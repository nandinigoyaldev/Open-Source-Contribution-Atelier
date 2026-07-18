from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"

    def ready(self):
        import apps.content.signals  # noqa: F401

        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("lesson_plugins")
