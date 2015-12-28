import os
from logging.config import dictConfig

PROJECT = os.path.expanduser('~/SuperDPF')
PATHS = {
    'conf_template': '{}/.conf_template.json'.format(PROJECT),
    'config': '{}/config.yml'.format(PROJECT),
    'photos': '{}/sdpf_photos'.format(PROJECT)
}

LOG_LOCATION = PROJECT
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
