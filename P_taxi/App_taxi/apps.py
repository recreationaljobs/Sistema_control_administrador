from django.apps import AppConfig  # type: ignore[reportMissingModuleSource]


class AppTaxiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_taxi'

    def ready(self):
        import App_taxi.auditoria_signals  # noqa: F401