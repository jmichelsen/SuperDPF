import boto3
import collections
import json
import os
import requests
import sys

from PIL import Image

from urlparse import urlsplit

from StringIO import StringIO

from BeautifulSoup import BeautifulStoneSoup

requests.packages.urllib3.disable_warnings()


class DPFConfigurator(object):
    PROJECT = os.path.expanduser('~/SuperDPF')
    PATHS = {
        'conf_template': '{}/.conf_template.json'.format(PROJECT),
        'config': '{}/config.json'.format(PROJECT),
        'photos': '{}/sdpf_photos'.format(PROJECT)
    }

    STORAGE_TYPES = ['aws', 'gphotos']

    def __init__(self):
        try:
            os.path.isfile(self.PATHS['config'])
        except:
            with open(self.PATHS['conf_template'], 'r') as template:
                template = json.load(template)
                template['first_run'] = ''
                with open(self.PATHS['config'], 'w') as config_file:
                    json.dump(template, config_file)

            self.create_photo_dirs()

    def create_photo_dirs(self):
        if not os.path.isdir(self.PATHS['photos']):
            os.makedirs(self.PATHS['photos'])


class BaseDPF(DPFConfigurator):
    @property
    def settings(self):
        try:
            os.path.isfile(self.PATHS['config'])
            with open(self.PATHS['config'], 'r') as config_file:
                config = json.load(config_file)
            return config
        except IOError as e:
            return e


class AWSController(BaseDPF):
    @property
    def aws_dir(self):
        return '{}/{}/'.format(self.PATHS['photos'], 'aws')
    
    @property
    def aws_configured(self):
        return bool(self.settings['aws'].get('access_key', False))

    @property
    def aws_enabled(self):
        return bool(self.settings['aws']['a_enabled'])

    def aws_configure_dialogue(self):
        access_key = raw_input('AWS Access Key: ')
        secret_key = raw_input('AWS Secret: ')
        bucket = raw_input('Bucket containing *only* dpf pics: ')
        enable = raw_input('Enter "yes" to enable AWS sync: ')

        enable = 'true' if enable.lower() == 'yes' else ''

        if not os.path.isdir(self.aws_dir):
            os.makedirs(self.aws_dir)

        self.save_settings(a_enabled=enable, access_key=access_key,
                           secret_key=secret_key, bucket=bucket)

    def aws_sync(self):
        if not self.aws_configured:
            print 'AWS is not configured.'
            configure = raw_input('Configure it now? ')
            if configure.lower() == 'yes':
                self.aws_configure_dialogue()
        elif not self.aws_enabled:
            print 'AWS is not enabled.'
            enable = raw_input('Enable it now? ')
            enable = 'true' if enable.lower() == 'yes' else ''
            self.save_settings(a_enabled=enable)
        else:
            bucket_name = self.settings['aws']['bucket']
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(bucket_name)

            for s3object in bucket.objects.iterator():
                filename = '{}/{}'.format(self.aws_dir, s3object.key)
                if not os.path.isfile(filename):
                    bucket.download_file(s3object.key, filename)


class GPhotoController(BaseDPF):
    @property
    def gphotos_dir(self):
        return '{}/{}/'.format(self.PATHS['photos'], 'gphotos')

    @property
    def gphotos_configured(self):
        return bool(self.settings['gphotos'].get('feed_url', False))

    @property
    def gphotos_enabled(self):
        return bool(self.settings['gphotos']['g_enabled'])

    def parse_feed_url(self, url):
        if urlsplit(url).path.startswith('/data/feed/'):
            return url
        elif urlsplit(url).netlock == 'picasaweb.google.com':
            response = requests.get(url)
            parsed = BeautifulStoneSoup(
                response.content, selfClosingTags=['meta', 'link', 'base'])

            for link in parsed.findAll('link'):
                if rel in link:
                    if link['rel'] == 'alternate':
                        return link['href']

    def gphotos_configure_dialogue(self):
        # https://picasaweb.google.com/data/feed/base/user/107119165375640000020/albumid/6225063173331304033?alt=rss&kind=photo&authkey=Gv1sRgCPzC_v7n98aRmgE&hl=en_US
        feed_url = self.parse_feed_url(raw_input('Google Photos Feed URL: '))
        user_id = raw_input('Google Photos Username: ')
        album_id = raw_input('Album ID: ')
        enable = raw_input('Enter "yes" to enable Google Photo sync: ')

        enable = 'true' if enable.lower() == 'yes' else ''

        if not os.path.isdir(self.gphotos_dir):
            os.makedirs(self.gphotos_dir)

        self.save_settings(g_enabled=enable, feed_url=feed_url,
                           user_id=user_id, album_id=album_id)

    def gphotos_sync(self):
        if not self.gphotos_configured:
            print 'Google Photos is not configured.'
            configure = raw_input('Configure it now? ')
            if configure.lower() == 'yes':
                self.gphotos_configure_dialogue()
        elif not self.gphotos_enabled:
            print 'Google Photos is not enabled.'
            enable = raw_input('Enable it now? ')
            enable = 'true' if enable.lower() == 'yes' else ''
            self.save_settings(g_enabled=enable)
        else:
            feed_url = self.settings['gphotos'].get('feed_url')
            response = requests.get(feed_url)
            tags = BeautifulStoneSoup(
                response.content).findAll('media:content')
            for tag in tags:
                if tag.get('url', False):
                    filename = os.path.join(
                        self.gphotos_dir,
                        os.path.basename(urlsplit(tag['url'])[2]))
                    if not os.path.isfile(filename):
                        print 'Getting img at {}'.format(tag['url'])
                        response = requests.get(tag['url'], stream=True)
                        try:
                            img = Image.open(StringIO(response.content))
                            img.save('{}'.format(filename))
                        except IOError:
                            pass


class FlickrController(BaseDPF):
    pass


class HotMediaController(BaseDPF):
    pass


class SuperDPF(AWSController, GPhotoController):
    def walk_json_tree(self, node, kwargs):
        for key, val in node.items():
            if isinstance(val, dict):
                self.walk_json_tree(val, kwargs)
            elif key in kwargs:
                node[key] = kwargs.get(key)
            else:
                continue
        return node

    def save_settings(self, **kwargs):
        config = self.walk_json_tree(self.settings, kwargs)

        with open(self.PATHS['config'], 'w') as config_file:
            json.dump(config, config_file)

    def sync(self):
        if self.aws_enabled:
            print 'Syncing AWS....'
            self.aws_sync()

        if self.gphotos_enabled:
            print 'Syncing Google Photos....'
            self.gphotos_sync()

    def run(self):
        self.sync()

if __name__ == "__main__":
    dpf = SuperDPF()
    dpf.run()
