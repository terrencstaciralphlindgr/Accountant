from django.apps import AppConfig


class PnLConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pnl'

    def ready(self):
        from . import signals
        from . import tasks
