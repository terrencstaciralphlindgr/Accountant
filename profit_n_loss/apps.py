from django.apps import AppConfig


class ProfitNLossConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profit_n_loss'

    def ready(self):
        from . import signals
        from . import tasks
