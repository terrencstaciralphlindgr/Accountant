from django.apps import AppConfig


class WidgetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'widget'

    def ready(self):
        from . import signals
        from . import tasks

