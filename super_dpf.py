import json
import os
import sys
import collections


class SuperDPF(object):
    PATHS = {'project': '/home/pi/SuperDPF'}
    PATHS['conf_template'] = \
        '{}/.sdpf_settings_template.json'.format(PATHS['project'])
    PATHS['config'] = '{}/config.json'.format(PATHS['project'])
    PATHS['photos'] = '{}/sdpf_photos'.format(PATHS['project'])

    STORAGE_TYPES = ['aws', 'gphotos']

    def __init__(self):
        if self.is_first_run:
            try:
                open(self.PATHS['config'], 'r')
            except:
                with open(self.PATHS['conf_template'], 'r') as template:
                    template = json.load(template)
                    template['first_run'] = ''
                    with open(self.PATHS['config'], 'w') as config_file:
                        json.dump(template, config_file)

            self.create_photo_dirs()
            self.set_storage_types()

    @property
    def settings(self):
        try:
            with open(self.PATHS['config'], 'r') as config_file:
                config = json.load(config_file)
            return config
        except IOError:
            print 'There was an error loading the settings file'
            return

    @property
    def is_first_run(self):
        if self.settings:
            return False
        return True

    @property
    def get_album_name(self):
        gphoto_settings = self.settings.get('gphotos')
        return gphoto_settings['album_name']

    @property
    def get_storage_types(self):
        storages = [self.settings.get('gphotos'),
                    self.settings.get('aws')]
        selected_storage = []
        for storage in storages:
            print storage
            print storage.get('enabled')
            if storage.get('a_enabled', False) or storage.get('g_enabled', False):
                selected_storage.append(storage)
        return selected_storage

    def set_album_name(self):
        album_name = raw_input('Enter album ID:')
        self.save_settings(album_name=album_name)

    def set_storage_types(self):
        selected_storage = {'aws': '', 'gphotos': ''}
        for service in self.STORAGE_TYPES:
            response = raw_input('Enter "yes" to enable {}:'.format(service))
            if response.lower() == 'yes':
                selected_storage[service] = response.lower()
            else:
                selected_storage[service] = ''
        self.save_settings(a_enabled=selected_storage['aws'],
                           g_enabled=selected_storage['gphotos'])

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

    def create_photo_dirs(self):
        if not os.path.exists(self.PATHS['photos']):
            os.makedirs(self.PATHS['photos'])

    def sync_aws(self):
        pass

    def sync_gphotos(self):
        pass

    def sync(self):
        self.sync_aws()
        self.sync_gphotos()

dpf = SuperDPF()

if dpf.is_first_run

'''
    bash calls sdpf
    --syncdpf checks config
    get config file: contains first run var, config vars
    --if first run:
        ask for storage type: aws, gphotos, both?
        if aws:
            ask for aws config
                set bucketname, secret key, api key as env variables OR in config file
        if google-photos:
            ask for gphoto ID
            ask for album name
            save config to config file
        create dirs (need to check for permissions, user)
        sync with online services

        if not first run
            sync with online services
'''