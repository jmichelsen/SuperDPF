from __future__ import division

import argparse
import boto3
import hashlib
import logging
import os
import requests
import sys
import traceback
import yaml

log = logging.getLogger('sdpf')

from PIL import Image, ImageFilter

from urlparse import urlsplit

from BeautifulSoup import BeautifulStoneSoup

from StringIO import StringIO

from constants import PATHS, UNSPLASH, IMAGE_EXTENSION,\
    FOREGROUND_SIZE, BACKGROUND_SIZE

requests.packages.urllib3.disable_warnings()


class SettingsItem:
    def __init__(self, name, title, value_type=str,
                 help_text=None, primary=False):
        self.name = name
        self.title = title
        self._help = help_text
        self.value_type = value_type
        self.primary = primary

    @property
    def help(self):
        if self._help:
            return self._help
        else:
            return self.title

    def value_dialog(self, old_value):
        if old_value:
            prompt = '{} [{}]:'.format(self.title, old_value)
            value = raw_input(prompt) or old_value
        else:
            value = raw_input('{}: '.format(self.title))
        if issubclass(self.value_type, basestring):
            return value
        elif self.value_type == int:
            return int(value)
        else:
            print('Unsupported value type: {}'.format(self.value_type))
            return None


class BaseDPF(object):
    REQUIRED_SETTINGS = list()

    def __init__(self, settings_object):
        self.settings = settings_object

    @property
    def subdir(self):
        pk_list = [str(s) for s in self.__class__.settings_pk(self.settings)]
        return '{}'.format('_'.join(pk_list))

    @classmethod
    def settings_dialog(cls, old_settings=dict()):
        settings_object = dict()
        for item in cls.REQUIRED_SETTINGS:
            settings_object[item.name] = item.value_dialog(
                old_settings.get(item.name))
        return settings_object

    @classmethod
    def settings_pk(cls, settings_object):
        pk_values = sorted({i.name for i
                            in cls.REQUIRED_SETTINGS if i.primary})
        pk = list()
        pk.append(cls.__name__)
        for value in pk_values:
            pk.append(settings_object.get(value))
        return pk

    def verify_local(self, cloud_filelist, local_filelist):
        for local_file in local_filelist:
            if local_file not in cloud_filelist:
                log.info('Deleting local file {}'.format(local_file))
                os.remove(local_file)

    def stylize_image(self, img):
        try:
            background = img.copy()

            w, h = img.size
            ratio = FOREGROUND_SIZE['height'] / h
            img = img.resize((int(w*ratio), int(h*ratio)))

            new_w, new_h = img.size
            background = background.resize(BACKGROUND_SIZE)
            background = background.filter(ImageFilter.GaussianBlur(radius=50))
            w2, h2 = background.size
            paste_dimensions = (((w2 - new_w)//2), ((h2 - new_h)//2))
            background.paste(img, paste_dimensions)

            return background
        except ValueError as e:
            log.info(
                'Styling failed. Saving original. Exception: {}'.format(e))
            return img

    @property
    def service_name(self):
        raise NotImplementedError('Implement service_name in subclass.')


class AmazonS3Resource(BaseDPF):
    REQUIRED_SETTINGS = [
        SettingsItem('aws_access_key', 'AWS Access Key'),
        SettingsItem('aws_secret', 'AWS Secret'),
        SettingsItem('bucket', 'Bucket containing *only* dpf pics',
                     primary=True),
    ]

    @property
    def service_name(self):
        return 'Amazon S3'

    def sync(self, verify_local):
        log.info('Syncing {}'.format(self.service_name))
        full_path = '{}/{}'.format(PATHS['photos'], self.subdir)
        duplicates = list()
        cloud_filelist = list()

        os.environ['AWS_ACCESS_KEY_ID'] = self.settings.get('aws_access_key')
        os.environ['AWS_SECRET_ACCESS_KEY'] = self.settings.get('aws_secret')

        buckets = []
        s3 = boto3.resource('s3')
        for s3bucket in s3.buckets.all():
            if 'dpf' in s3bucket.name:
                buckets.append(s3bucket.name)

        if self.settings['bucket'] not in buckets:
            buckets.append(self.settings['bucket'])

        for bucket in buckets:
            s3bucket = s3.Bucket(bucket)
            for s3object in s3bucket.objects.iterator():
                filename = os.path.join(full_path, s3object.key)
                cloud_filelist.append(filename)
                if not os.path.isfile(filename):
                    log.info('Downloading {}'.format(s3object.key))
                    try:
                        s3bucket.download_file(s3object.key, filename)
                    except IOError as e:
                        log.error(e)
                else:
                    duplicates.append(s3object.key)

        if duplicates:
            log.info(
                'Skipped {} duplicate images from {}.'.format(
                    len(duplicates), self.service_name))

        if verify_local:
            local_filelist = \
                [os.path.join(full_path, f) for f in os.listdir(full_path)]
            self.verify_local(cloud_filelist, local_filelist)
            log.info('Local {} files verified successfully.'.format(
                self.service_name))

        if not cloud_filelist:
            log.info('{} has nothing to sync.'.format(self.service_name))

        log.info('Done syncing {}'.format(self.service_name))


class GPhotoResource(BaseDPF):
    REQUIRED_SETTINGS = [
        SettingsItem('feed_url', 'Feed URL'),
        SettingsItem('user_id', 'Google Photos Username', primary=True),
        SettingsItem('album_id', 'Album ID'),
    ]

    @property
    def service_name(self):
        return 'Google Photos'

    @staticmethod
    def _parse_feed_url(url):
        if urlsplit(url).path.startswith('/data/feed/'):
            return url
        elif urlsplit(url).netlock == 'picasaweb.google.com':
            response = requests.get(url)
            parsed = BeautifulStoneSoup(
                response.content, selfClosingTags=['meta', 'link', 'base'])

            for link in parsed.findAll('link'):
                if 'rel' in link:
                    if link['rel'] == 'alternate':
                        return link['href']

    def sync(self, verify_local):
        log.info('Syncing {}'.format(self.service_name))
        full_path = '{}/{}'.format(PATHS['photos'], self.subdir)
        duplicates = list()
        cloud_filelist = list()

        response = requests.get(self.settings.get('feed_url'))
        tags = BeautifulStoneSoup(
            response.content).findAll('media:content')
        for tag in tags:
            if tag.get('url', False):
                filename = os.path.join(
                    full_path, os.path.basename(urlsplit(tag['url'])[2]))
                cloud_filelist.append(filename)
                if not os.path.isfile(filename):
                    log.info(
                        'Getting img at {}'.format(tag['url']))
                    response = requests.get(tag['url'], stream=True)
                    try:
                        img = Image.open(StringIO(response.content))
                        if img.height > img.width:
                            img = self.stylize_image(img)
                        img.save('{}'.format(filename), optimize=True,
                                 progressive=True, quality=100,
                                 subsampling=0)
                    except IOError as e:
                        log.error(e)
                else:
                    duplicates.append(tag)

        if duplicates:
            log.info(
                'Skipped {} duplicate images from {}.'.format(
                    len(duplicates), self.service_name))

        if verify_local:
            local_filelist = \
                [os.path.join(full_path, f) for f in os.listdir(full_path)]
            self.verify_local(cloud_filelist, local_filelist)
            log.info('Local {} files verified successfully.'.format(
                self.service_name))

        if not cloud_filelist:
            log.info('{} has nothing to sync.'.format(self.service_name))

        log.info('Done syncing {}'.format(self.service_name))


class UnsplashResource(BaseDPF):
    REQUIRED_SETTINGS = [
        SettingsItem('preferred_res', 'Preferred Resolution',
                     help_text='eg 1600x900'),
        SettingsItem('category', 'Unsplash Category',
                     help_text='choices: buildings, food, nature, people,'
                               ' technology, objects, none', primary=True)
    ]

    @property
    def service_name(self):
        return 'Unsplash'

    def sync(self, verify_local):
        log.info('Syncing {}'.format(self.service_name))
        full_path = '{}/{}'.format(PATHS['photos'], self.subdir)
        duplicates = list()

        if self.settings.get('category') == 'none' or False:
            url = '{}/{}/{}'.format(UNSPLASH['base'], UNSPLASH['random'],
                                    self.settings.get('preferred_res'))
        else:
            url = '{}/{}/{}/{}'.format(UNSPLASH['base'], UNSPLASH['category'],
                                       self.settings.get('category'),
                                       self.settings.get('preferred_res'))

        response = requests.get(url)
        img_hash = hashlib.md5(response.request.path_url).hexdigest()
        filename = os.path.join(
            full_path, '{}.{}'.format(img_hash, IMAGE_EXTENSION))
        if not os.path.isfile(filename):
            log.info('Getting img at {}'.format(response.url))
            try:
                img = Image.open(StringIO(response.content))
                if img.height > img.width:
                    img = self.stylize_image(img)
                img.save('{}'.format(filename), 'JPEG', optimize=True,
                         progressive=True, quality=100, subsampling=0)
            except IOError as e:
                log.error(e)
        else:
            duplicates.append(filename)

        if duplicates:
            log.info(
                'Skipped {} duplicate images from {}'.format(
                    len(duplicates), self.service_name))

        log.info('Done syncing {}'.format(self.service_name))


class DropboxController(BaseDPF):
    pass


class FlickrController(BaseDPF):
    # https://stuvel.eu/media/flickrapi-docs/documentation/
    pass


class InstagramController(BaseDPF):
    # https://github.com/Instagram/python-instagram
    pass


class HotMediaController(BaseDPF):
    pass


class ExitConfig(Exception):
    pass


class DPFConfigurator(object):
    ACCOUNT_TYPES = [
        AmazonS3Resource,
        GPhotoResource,
        UnsplashResource
    ]

    def __init__(self):
        if not os.path.isfile(PATHS['config']):
            log.info('Initializing empty config...')
            with open(PATHS['config'], 'w') as config_file:
                yaml.dump(dict(), config_file)
            self.config_dict = dict()

        else:
            with open(PATHS['config']) as config:
                self.config_dict = yaml.load(config)

        if not os.path.isdir(PATHS['logs']):
            os.makedirs(PATHS['logs'])

        self.config_dict.setdefault('accounts', list())
        self._create_photo_dirs()

    def get_account_class_dict(self):
        return {k.__name__: k for k in self.ACCOUNT_TYPES}

    def get_account_class(self, class_name):
        return self.get_account_class_dict().get(class_name)

    def save(self):
        # serialize before we open the file (and truncate) in write mode
        yaml_str = yaml.dump(self.config_dict)
        with open(PATHS['config'], 'w') as config:
            config.write(yaml_str)

    @property
    def accounts(self):
        return self.config_dict.get('accounts')

    def add_account(self, klass, settings_dict):
        if klass not in self.ACCOUNT_TYPES:
            print('Unsupported account type! {}'.format(klass.__name__))
            return
        self.config_dict['accounts'].append((klass.__name__, settings_dict))

    def replace_account(self, klass, settings_dict, index):
        if klass not in self.ACCOUNT_TYPES:
            print('Unsupported account type! {}'.format(klass.__name__))
            return
        self.config_dict['accounts'][index] = (klass.__name__, settings_dict)

    def add_account_dialog(self):
        account_types = sorted(self.get_account_class_dict().keys())
        print('Valid account types: {}'.format(', '.join(account_types)))
        account_type = raw_input('Account type: ')
        account_class = self.get_account_class(account_type)
        if account_class:
            settings = account_class.settings_dialog()
            self.add_account(account_class, settings)
            self.save()
        else:
            print('{} was not a valid account type.'.format(account_type))

    def edit_account_dialog(self):
        account_list = list()
        account_dict = dict()
        for index, account_entry in enumerate(self.accounts):
            account_dict[str(index)] = account_entry
            line = '\t{}\t{}: {}'.format(index, *account_entry)
            account_list.append(line)

        print('Current accounts:\n{}'.format('\n'.join(account_list)))
        print('\t+\tAdd new account')
        print('\tq\tQuit')
        account_number = raw_input('Enter account number to edit: ')
        if account_number == '+':
            self.add_account_dialog()
        elif account_number == 'q':
            raise ExitConfig()
        elif account_dict.get(account_number):
            class_name, old_settings = account_dict.get(account_number)
            account_class = self.get_account_class(class_name)
            if account_class:
                settings = account_class.settings_dialog(old_settings)
                self.replace_account(account_class, settings,
                                     int(account_number))
                self.save()
            else:
                print("Couldn't resolve account class type: {}"
                      .format(class_name))
        else:
            print('Invalid entry: {}'.format(account_number))

    def _create_photo_dirs(self):
        if not os.path.isdir(PATHS['photos']):
            os.makedirs(PATHS['photos'])
        for class_name, settings_object in self.accounts:
            klass = self.get_account_class(class_name)
            dpf_instance = klass(settings_object)
            account_path = os.path.join(PATHS['photos'],
                                        dpf_instance.subdir)
            if not os.path.isdir(account_path):
                log.info(
                    '{} directory missing. Creating.'.format(class_name))
                os.makedirs(account_path)


class SuperDPF(object):
    def __init__(self):
        self.config = DPFConfigurator()

    def sync(self, restart_sdpf=False, verify_local=False):
        log.info('{} accounts to sync..'.format(len(self.config.accounts)))
        for klass, config in self.config.accounts:
            pk = None
            klass = self.config.get_account_class(klass)
            try:
                pk = klass.settings_pk(config)
                instance = klass(config)
                instance.sync(verify_local)
            except Exception as e:
                msg = 'Error syncing {} ({}): {}'
                traceback.print_exc()
                log.error(msg.format(klass.__name__, pk, e))
        if restart_sdpf:
            log.info('Restarting SDPF')
            os.system('killall fim')

    def configure(self):
        try:
            while True:
                self.config.edit_account_dialog()
        except ExitConfig:
            pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SuperDPF')
    parser.add_argument('--configure',
                        action='store_true',
                        dest='configure',
                        default=False,
                        help='Enter configuration mode')
    parser.add_argument('--sync',
                        action='store_true',
                        dest='sync',
                        default=False,
                        help='Synchronize photos')
    parser.add_argument('--verify-local',
                        action='store_true',
                        dest='verify_local',
                        default=False,
                        help='Verify and remove local files not found in sync')
    parser.add_argument('--restart-sdpf',
                        action='store_true',
                        dest='restart_sdpf',
                        default=False,
                        help='Restart sdpf after sync')
    args = parser.parse_args(sys.argv[1:])
    dpf = SuperDPF()
    if args.configure:
        dpf.configure()
    elif args.sync:
        dpf.sync(args.restart_sdpf, args.verify_local)
    else:
        parser.print_help()
