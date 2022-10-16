from __future__ import absolute_import
import os
from celery import Celery
from pprint import pprint
from django.conf import settings
from kombu import Queue
import logging
import structlog
from django_structlog.celery.steps import DjangoStructLogInitStep
from celery.signals import setup_logging
from django_structlog.celery import signals
from django_structlog.signals import bind_extra_request_metadata
from django.dispatch import receiver

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
                    "processor": structlog.processors.JSONRenderer(),
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
                    "processor": structlog.dev.ConsoleRenderer(),
                },
                "key_value": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.KeyValueRenderer(
                        key_order=['timestamp', 'level', 'event', 'logger']),
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
                    'maxBytes': 1024 * 1024 * 100,  # 100 mb
                },
                "flat_line_file": {
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": "logs/flat_line.log",
                    "formatter": "key_value",
                    'maxBytes': 1024 * 1024 * 100,  # 100 mb
                },
            },
            "loggers": {
                # "": {
                #     "handlers": ["console", "flat_line_file", "json_file"],
                #     "level": "INFO",
                #     'propagate': False
                # },
                # "django_structlog": {
                #     "handlers": ["console"],  # , "flat_line_file", "json_file"],
                #     "level": "INFO",
                #     'propagate': True
                # },
                # "authentication": {
                #     "handlers": ["console", "flat_line_file", "json_file"],
                #     "level": "INFO",
                #     'propagate': False
                # },
                # "pnl": {
                #     "handlers": ["console", "flat_line_file", "json_file"],
                #     "level": "DEBUG",
                #     'propagate': False
                # },
                # "market": {
                #     "handlers": ["console"],  # , "flat_line_file", "json_file"],
                #     "level": "INFO",
                #     'propagate': False
                # },
                "account": {
                    "handlers": ["console"],  # , "flat_line_file", "json_file"],
                    "level": "INFO",
                    'propagate': False
                },
                # "statistics": {
                #     "handlers": ["console", "flat_line_file", "json_file"],
                #     "level": "INFO",
                #     'propagate': False
                # }
            }
        }
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# @setup_logging.connect
# def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # pragma: no cover
#     from logging.config import dictConfig
#     from django.conf import settings
#     dictConfig(settings.LOGGING)

# logging.config.dictConfig(
#     {
#         "version": 1,
#         "disable_existing_loggers": False,
#         "formatters": {
#             "json_formatter": {
#                 "()": structlog.stdlib.ProcessorFormatter,
#                 "processor": structlog.processors.JSONRenderer(sort_keys=False),
#                 "foreign_pre_chain": [
#                     structlog.contextvars.merge_contextvars,
#                     structlog.processors.TimeStamper(fmt="iso"),
#                     structlog.stdlib.add_logger_name,
#                     structlog.stdlib.add_log_level,
#                     structlog.stdlib.PositionalArgumentsFormatter(),
#                 ],
#             },
#             "plain_console": {
#                 "()": structlog.stdlib.ProcessorFormatter,
#                 "processor": structlog.dev.ConsoleRenderer(pad_event=43, colors=True, force_colors=True),
#             },
#             "key_value": {
#                 "()": structlog.stdlib.ProcessorFormatter,
#                 "processor": structlog.processors.KeyValueRenderer(sort_keys=False,
#                                                                    key_order=['level',
#                                                                               'logger',
#                                                                               'timestamp',
#                                                                               'event']),
#             },
#         },
#         "handlers": {
#             "console": {
#                 "class": "logging.StreamHandler",
#                 "formatter": "plain_console",
#             },
#         },
#         "loggers": {
#             "authentication": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#             "pnl": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#             "market": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#             "account": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#             "statistics": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#             "widget": {
#                 "handlers": ["console", "flat_line_file", "json_file"],
#                 "level": "INFO",
#                 'propagate': False,
#             },
#         }
#     }
# )
#
#     structlog.configure(
#         processors=[
#             # structlog.contextvars.merge_contextvars,
#             # structlog.stdlib.filter_by_level,
#             # structlog.processors.TimeStamper(fmt="iso"),
#             # structlog.stdlib.add_logger_name,
#             # structlog.stdlib.add_log_level,
#             # structlog.stdlib.PositionalArgumentsFormatter(),
#             # structlog.processors.StackInfoRenderer(),
#             # structlog.processors.format_exc_info,
#             # structlog.processors.UnicodeDecoder(),
#             # structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
#         ],
#         # context_class=dict,
#         # wrapper_class=structlog.stdlib.BoundLogger,
#         logger_factory=structlog.stdlib.LoggerFactory(),
#         cache_logger_on_first_use=True,
#     )


# @receiver(bind_extra_request_metadata)
# def bind_unbind_metadata(request, logger, **kwargs):
#     structlog.contextvars.unbind_contextvars('task_id', 'parent_task_id', 'ip', 'user_id', 'request_id',)
#     logger.try_unbind('task_id', 'parent_task_id', 'ip', 'user_id', 'request_id',)
#
#
# @receiver(signals.modify_context_before_task_publish)
# def receiver_modify_context_before_task_publish(sender, signal, context, **kwargs):
#     structlog.contextvars.unbind_contextvars('task_id', 'parent_task_id')

#     keys_to_keep = {}
#     new_dict = {key_to_keep: context[key_to_keep] for key_to_keep in keys_to_keep if key_to_keep in context}
#     context.clear()
#     context.update(new_dict)
