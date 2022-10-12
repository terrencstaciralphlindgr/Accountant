import os
import structlog
import logging
from datetime import timedelta
from django.conf.locale.en import formats as en_formats
from accountant.methods import get_env

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Contains manage.py and PROJECT_ROOT
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # Contains settings.py

env = get_env()
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS').split()

INSTALLED_APPS = [
    'account.apps.AccountConfig',
    'authentication.apps.AuthenticationConfig',
    'pnl.apps.PnLConfig',
    'statistic.apps.StatisticConfig',
    'market.apps.MarketConfig',
    'widget.apps.WidgetConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'django_celery_beat',
    'prettyjson',
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'admincharts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_structlog.middlewares.RequestMiddleware',
    'django_structlog.middlewares.CeleryMiddleware',
]

ROOT_URLCONF = 'accountant.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'accountant.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('ACCOUNTANT_DB_NAME'),
        'HOST': env('ACCOUNTANT_DB_HOST'),
        'PORT': env('ACCOUNTANT_DB_PORT'),
        'USER': env('ACCOUNTANT_DB_USER'),
        'PASSWORD': env('ACCOUNTANT_DB_PASSWORD'),
        'OPTIONS': {'sslmode': 'require',
                    'sslrootcert': 'strategy/ssl/default/ca-certificate.crt',
                    },
    }
}

CONN_MAX_AGE = 0

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CELERY_TASK_ALWAYS_EAGER=True
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER', 'redis://127.0.0.1:6375/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_BACKEND', 'redis://127.0.0.1:6375/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_IMPORTS = ('authentication.tasks', 'pnl.tasks', 'statistic.tasks', 'account.tasks', 'market.tasks')

en_formats.DATETIME_FORMAT = 'Y-m-d H:i:s'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "formatters": {
#         "json_formatter": {
#             "()": structlog.stdlib.ProcessorFormatter,
#             "processor": structlog.processors.JSONRenderer(sort_keys=False),
#             "foreign_pre_chain": [
#                 structlog.contextvars.merge_contextvars,
#                 structlog.processors.TimeStamper(fmt="iso"),
#                 structlog.stdlib.add_logger_name,
#                 structlog.stdlib.add_log_level,
#                 structlog.stdlib.PositionalArgumentsFormatter(),
#             ],
#         },
#         "plain_console": {
#             "()": structlog.stdlib.ProcessorFormatter,
#             "processor": structlog.dev.ConsoleRenderer(pad_event=43, colors=True, force_colors=True),
#         },
#         "key_value": {
#             "()": structlog.stdlib.ProcessorFormatter,
#             "processor": structlog.processors.KeyValueRenderer(key_order=['level',
#                                                                           'logger',
#                                                                           'event',
#                                                                           'timestamp'],
#                                                                sort_keys=False
#             ),
#         },
#     },
#     "handlers": {
#         "console": {
#             "class": "logging.StreamHandler",
#             "formatter": "plain_console",
#         },
#         "json_file": {
#             "class": "logging.handlers.WatchedFileHandler",
#             "filename": "logs/json.log",
#             "formatter": "json_formatter",
#         },
#         "flat_line_file": {
#             "class": "logging.handlers.WatchedFileHandler",
#             "filename": "logs/flat_line.log",
#             "formatter": "key_value",
#         },
#     },
#     "loggers": {
#         "authentication": {
#             "handlers": ["console", "flat_line_file", "json_file"],
#             "level": "INFO",
#         },
#         "pnl": {
#             "handlers": ["console", "flat_line_file", "json_file"],
#             "level": "DEBUG",
#         },
#         "market": {
#             "handlers": ["console", "flat_line_file", "json_file"],
#             "level": "INFO",
#         },
#         "account": {
#             "handlers": ["console", "flat_line_file", "json_file"],
#             "level": "INFO",
#         },
#         "statistics": {
#             "handlers": ["console", "flat_line_file", "json_file"],
#             "level": "INFO",
#         }
#     }
# }
#
# structlog.configure(
#     processors=[
#         structlog.contextvars.merge_contextvars,
#         structlog.stdlib.filter_by_level,
#         structlog.processors.TimeStamper(fmt="iso"),  #
#         structlog.stdlib.add_logger_name,
#         structlog.stdlib.add_log_level,
#         structlog.stdlib.PositionalArgumentsFormatter(),
#         structlog.processors.StackInfoRenderer(),
#         structlog.processors.format_exc_info,
#         structlog.processors.UnicodeDecoder(),
#         structlog.processors.ExceptionPrettyPrinter(),
#         structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
#     ],
#     logger_factory=structlog.stdlib.LoggerFactory(),
#     cache_logger_on_first_use=True,
# )

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
pre_chain = [
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    # Add extra attributes of LogRecord objects to the event dictionary
    # so that values passed in the extra parameter of log methods pass
    # through to log output.
    structlog.stdlib.ExtraAdder(),
    timestamper,
]


def extract_from_record(_, __, event_dict):
    """
    Extract thread and process names and add them to the event dict.
    """
    record = event_dict["_record"]
    event_dict["thread_name"] = record.threadName
    event_dict["process_name"] = record.processName

    return event_dict


from logging.config import dictConfig

dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                   structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                   structlog.dev.ConsoleRenderer(colors=False),
                ],
                "foreign_pre_chain": pre_chain,
            },
            "colored": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                   extract_from_record,
                   structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                   structlog.dev.ConsoleRenderer(colors=True),
                ],
                "foreign_pre_chain": pre_chain,
            },
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "colored",
            },
            "file": {
                "level": "DEBUG",
                "class": "logging.handlers.WatchedFileHandler",
                "filename": "test.log",
                "formatter": "plain",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default", "file"],
                "level": "DEBUG",
                "propagate": True,
            },
        }
})
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


AUTH_USER_MODEL = 'authentication.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'authentication.backends.JWTAuthentication',
    'authentication.backends.EmailAdminBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=365 * 99),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=365 * 99),
    'USER_ID_CLAIM': 'user_id',
    'USER_ID': 'user_id'
}

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


CODES = {
    'binance': {
        'supported_quote': ['USDT', 'BUSD'],
        'supported_base': ['BTC']
    },
    'ftx': {
        'supported_quote': ['USD'],
        'supported_base': ['BTC']
    }
}

EXCHANGES = {
    'ftx': {
        'default': {
            'markets': {
                'methods': ['watch_ticker'],
                'private': False,
                'instruments': [
                    {'base': 'BTC',
                     'quote': 'USD',
                     'type': 'spot'
                     },
                    {'base': 'BTC',
                     'quote': 'USD',
                     'type': 'perpetual'
                     }
                ]
            }
        }
    }
}