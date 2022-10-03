from django.apps import AppConfig


class StatisticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'statistic'

    def ready(self):
        from . import signals
        from . import tasks

