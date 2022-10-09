from __future__ import absolute_import
import os
from celery import Celery
from pprint import pprint
from django.conf import settings
from kombu import Queue
import logging
import structlog
from django_structlog.celery.steps import DjangoStructLogInitStep
from django_structlog.celery import signals
from django_structlog.signals import bind_extra_request_metadata
from django.dispatch import receiver
from celery.signals import setup_logging, after_setup_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accountant.settings')

app = Celery("accountant", broker='redis://localhost:6375/0')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Queuing
app.conf.task_default_queue = 'accountant_queue_1'
CELERY_TASK_CREATE_MISSING_QUEUES = False
CELERY_TASK_QUEUES = (
    Queue('default'),
    Queue('accountant_queue_1'),
    Queue('accountant_queue_2'),
)

# A step to initialize django-structlog
app.steps['worker'].add(DjangoStructLogInitStep)


@setup_logging.connect
def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # pragma: no cover
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(sort_keys=False),
                },
                "plain_console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(pad_event=43, colors=True, force_colors=True),
                },
                "key_value": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.KeyValueRenderer(sort_keys=False,
                                                                       key_order=['level',
                                                                                  'logger',
                                                                                  'timestamp',
                                                                                  'event']),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "plain_console",
                },
            },
            "loggers": {
                '': {
                    "handlers": ["console", "flat_line_file", "json_file"],
                    "level": "WARNING",
                    'propagate': False,
                },
                "authentication": {
                    "handlers": ["console", "flat_line_file", "json_file"],
                    "level": "INFO",
                    'propagate': False,
                },
                "strategy": {
                    "handlers": ["console", "flat_line_file", "json_file"],
                    "level": "INFO",
                    'propagate': False,
                },
                "trading": {
                    "handlers": ["console", "flat_line_file", "json_file"],
                    "level": "INFO",
                    'propagate': False,
                },
                "market": {
                    "handlers": ["console", "flat_line_file", "json_file"],
                    "level": "INFO",
                    'propagate': False,
                },
            }
        }
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f"),  # (fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=structlog.threadlocal.wrap_dict(dict),
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@receiver(bind_extra_request_metadata)
def bind_unbind_metadata(request, logger, **kwargs):
    logger.unbind('request_id', 'ip', 'user_id')

