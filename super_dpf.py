import argparse
import boto3
import json
import logging
from logging.config import dictConfig
import os
import requests

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

    def __init__(self):
        if not os.path.isfile(self.PATHS['config']):
            logging.info('Initializing config...')
            with open(self.PATHS['conf_template'], 'r') as template:
                template = json.load(template)
                with open(self.PATHS['config'], 'w') as config_file:
                    json.dump(template, config_file)

            self._create_photo_dirs()

    def _create_photo_dirs(self):
        if not os.path.isdir(self.PATHS['photos']):
            os.makedirs(self.PATHS['photos'])

    def _walk_json_tree(self, node, kwargs):
        for key, val in node.items():
            if isinstance(val, dict):
                self._walk_json_tree(val, kwargs)
            elif key in kwargs:
                node[key] = kwargs.get(key)
            else:
                continue
        return node


class LogManager(object):
    LOG_LOCATION = os.path.dirname(os.path.realpath(__file__))
    LOGGING = {
        'version': 1,
        'formatters': {
            'standard': {
                'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
                'datefmt': "%d/%b/%Y %H:%M:%S"
            },
            'verbose': {
                'format': 'dpf[%(process)d]: %(levelname)s %(name)s[%(module)s] %(message)s'
            },
        },
        'handlers': {
            'null': {
                'level': 'DEBUG',
                'class': 'logging.NullHandler',
            },
            # 'mail_admins': {
            #     'level': 'ERROR',
            #     'class': 'logging.handlers.AdminEmailHandler'
            # },
            'logfile': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '{}/sdpf.log'.format(LOG_LOCATION),
                'maxBytes': 50000000,
                'backupCount': 2,
                'formatter': 'standard',
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'standard'
            },
            'syslog': {
                'level': 'INFO',
                'class': 'logging.handlers.SysLogHandler',
                'formatter': 'verbose',
                'address': '/dev/log',
                'facility': 'local2',
            }
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'syslog'],
                'propagate': True,
                'level': 'WARN',
            },
            'urllib3': {
                'handlers': ['console', 'logfile', 'syslog'],
                'propagate': True,
                'level': 'ERROR',
            },
            '': {
                'handlers': ['console', 'logfile', 'syslog'],
                'propagate': True,
                'level': 'DEBUG',
            },
        }
    }

    dictConfig(LOGGING)


class BaseDPF(DPFConfigurator, LogManager):
    @property
    def settings(self):
        try:
            with open(self.PATHS['config'], 'r') as config_file:
                config = json.load(config_file)
            return config
        except IOError as e:
            logging.error(e)

    def _save_settings(self, **kwargs):
        config = self._walk_json_tree(self.settings, kwargs)
        with open(self.PATHS['config'], 'w') as config_file:
            json.dump(config, config_file)


class AWSController(BaseDPF):
    @property
    def aws_dir(self):
        return '{}/{}'.format(self.PATHS['photos'], 'aws')
    
    @property
    def aws_configured(self):
        return bool(self.settings['aws'].get('access_key', False))

    @property
    def aws_enabled(self):
        try:
            if os.path.isfile(self.PATHS['config']):
                return bool(self.settings['aws']['a_enabled'])
        except RuntimeWarning as e:
            logging.error('Settings have not been initiated. {}'.format(e))

    def aws_configure_dialogue(self):
        access_key = raw_input('AWS Access Key: ')
        secret_key = raw_input('AWS Secret: ')
        bucket = raw_input('Bucket containing *only* dpf pics: ')
        enable = raw_input('Enter "yes" to enable AWS sync: ')

        enable = 'true' if enable.lower() == 'yes' else ''

        if not os.path.isdir(self.aws_dir):
            os.makedirs(self.aws_dir)

        os.environ['AWS_ACCESS_KEY_ID'] = access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key

        self._save_settings(a_enabled=enable, access_key=access_key,
                            secret_key=secret_key, bucket=bucket)

    def _aws_sync(self):
        if not self.aws_configured:
            logging.info('AWS is not configured.')
            configure = raw_input('Configure it now? ')
            if configure.lower() == 'yes':
                self.aws_configure_dialogue()
        elif not self.aws_enabled:
            logging.info('AWS is not enabled.')
            enable = raw_input('Enable it now? ')
            enable = 'true' if enable.lower() == 'yes' else ''
            self._save_settings(a_enabled=enable)
        else:
            aws_settings = self.settings['aws']
            os.environ['AWS_ACCESS_KEY_ID'] = aws_settings['access_key']
            os.environ['AWS_SECRET_ACCESS_KEY'] = aws_settings['secret_key']

            buckets = []
            s3 = boto3.resource('s3')
            for s3bucket in s3.buckets.all():
                if 'dpf' in s3bucket.name:
                    buckets.append(s3bucket.name)

            if self.settings['aws']['bucket'] not in buckets:
                buckets.append(self.settings['aws']['bucket'])

            for bucket in buckets:
                s3bucket = s3.Bucket(bucket)
                for s3object in s3bucket.objects.iterator():
                    filename = '{}/{}'.format(self.aws_dir, s3object.key)
                    if not os.path.isfile(filename):
                        logging.info('Downloading {}'.format(s3object.key))
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
        try:
            if os.path.isfile(self.PATHS['config']):
                return bool(self.settings['gphotos']['g_enabled'])
        except RuntimeWarning as e:
            logging.error('Settings have not been initiated. {}'.format(e))

    def _parse_feed_url(self, url):
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

    def gphotos_configure_dialogue(self):
        # https://picasaweb.google.com/data/feed/base/user/107119165375640000020/albumid/6225063173331304033?alt=rss&kind=photo&authkey=Gv1sRgCPzC_v7n98aRmgE&hl=en_US
        feed_url = self._parse_feed_url(raw_input('Google Photos Feed URL: '))
        user_id = raw_input('Google Photos Username: ')
        album_id = raw_input('Album ID: ')
        enable = raw_input('Enter "yes" to enable Google Photo sync: ')

        enable = 'true' if enable.lower() == 'yes' else ''

        if not os.path.isdir(self.gphotos_dir):
            os.makedirs(self.gphotos_dir)

        self._save_settings(g_enabled=enable, feed_url=list(feed_url),
                            user_id=user_id, album_id=album_id)

    def _gphotos_sync(self):
        if not self.gphotos_configured:
            logging.info('Google Photos is not configured.')
            configure = raw_input('Configure it now? ')
            if configure.lower() == 'yes':
                self.gphotos_configure_dialogue()
        elif not self.gphotos_enabled:
            logging.info('Google Photos is not enabled.')
            enable = raw_input('Enable it now? ')
            enable = 'true' if enable.lower() == 'yes' else ''
            self._save_settings(g_enabled=enable)
        else:
            feed_url = self.settings['gphotos'].get('feed_url')
            for feed in feed_url:
                response = requests.get(feed)
                tags = BeautifulStoneSoup(
                    response.content).findAll('media:content')
                for tag in tags:
                    if tag.get('url', False):
                        filename = os.path.join(
                            self.gphotos_dir,
                            os.path.basename(urlsplit(tag['url'])[2]))
                        if not os.path.isfile(filename):
                            logging.info(
                                'Getting img at {}'.format(tag['url']))
                            response = requests.get(tag['url'], stream=True)
                            try:
                                img = Image.open(StringIO(response.content))
                                img.save('{}'.format(filename))
                            except IOError as e:
                                logging.error(e)


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


class SuperDPF(AWSController, GPhotoController):
    def _sync(self):
        if self.aws_enabled:
            logging.info('Syncing AWS....')
            self._aws_sync()

        if self.gphotos_enabled:
            logging.info('Syncing Google Photos....')
            self._gphotos_sync()

    def run(self):
        self._sync()

if __name__ == "__main__":
    dpf = SuperDPF()
    dpf.run()
