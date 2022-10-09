import os
import structlog
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
CELERY_IMPORTS = ('authentication.tasks', 'pnl.tasks', 'statistic.tasks', 'account.tasks', 'widget.tasks',)

en_formats.DATETIME_FORMAT = 'Y-m-d H:i:s'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(sort_keys=False),
            "foreign_pre_chain": [
                structlog.contextvars.merge_contextvars,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
            ],
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(pad_event=43, colors=True, force_colors=True),
        },
        "key_value": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.KeyValueRenderer(key_order=['level',
                                                                          'logger',
                                                                          'event',
                                                                          'timestamp'],
                                                               sort_keys=False
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
        "json_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": "logs/json.log",
            "formatter": "json_formatter",
        },
        "flat_line_file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": "logs/flat_line.log",
            "formatter": "key_value",
        },
    },
    "loggers": {
        "authentication": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
            'propagate': False,
        },
        "pnl": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "DEBUG",
            'propagate': False,
        },
        "market": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
            'propagate': False,
        },
        "account": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
            'propagate': False,
        },
        "statistics": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
            'propagate': False,
        },
        "widget": {
            "handlers": ["console", "flat_line_file", "json_file"],
            "level": "INFO",
            'propagate': False,
        },
    }
}

structlog.configure(
    processors=[
        # structlog.contextvars.merge_contextvars,
        # structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        # structlog.processors.add_log_level,  # ***
        # structlog.stdlib.PositionalArgumentsFormatter(),
        # structlog.processors.StackInfoRenderer(),
        # structlog.processors.format_exc_info,
        # structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    # context_class=dict,
    # wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    # cache_logger_on_first_use=True,
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

EXCHANGES = {
    'binance': {
        'supported_quote': ['USDT', 'BUSD'],
        'supported_base': ['BTC']
    },
    'ftx': {
        'supported_quote': ['USD'],
        'supported_base': ['BTC']
    }
}

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

