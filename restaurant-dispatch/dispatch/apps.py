from django.apps import AppConfig


class DispatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dispatch"
    verbose_name = "Syncora dispatch"

    def ready(self):
        from . import checks  # noqa: F401  (registers deployment checks)
