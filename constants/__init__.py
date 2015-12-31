import os
from logging.config import dictConfig

FOREGROUND_SIZE = {'width': 0, 'height': 1100}
BACKGROUND_SIZE = (1600, 1200)

IMAGE_EXTENSION = 'jpg'

UNSPLASH = {
    'base': 'https://source.unsplash.com',
    'random': 'random',
    'category': 'category'
}

PROJECT = os.path.expanduser('~/SuperDPF')
PATHS = {
    'conf_template': '{}/.conf_template.json'.format(PROJECT),
    'config': '{}/config.yml'.format(PROJECT),
    'photos': '{}/sdpf_photos'.format(PROJECT),
    'logs': '{}/logs'.format(PROJECT)
}


LOG_LOCATION = os.path.join(PROJECT, 'logs')
LOGGING = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%d/%b/%Y %H:%M:%S'
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
        'logfile': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': '{}/sdpf.log'.format(LOG_LOCATION),
            'when': 'midnight',
            'backupCount': 7,
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
        'urllib3': {
            'handlers': ['console', 'logfile', 'syslog'],
            'propagate': True,
            'level': 'ERROR',
        },
        'sdpf': {
            'handlers': ['console', 'logfile'],
            'propagate': False,
            'level': 'DEBUG',
        },
        '': {
            'handlers': ['console', 'logfile', 'syslog'],
            'propagate': True,
            'level': 'DEBUG',
        },
    }
}

dictConfig(LOGGING)
