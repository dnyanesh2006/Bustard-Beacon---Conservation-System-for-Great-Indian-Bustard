from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Bustard Beacon Core'

    def ready(self):
        """
        Signal handlers and startup configuration would be registered here.
        """
        pass
