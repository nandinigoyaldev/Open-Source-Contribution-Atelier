from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organizations"

    def ready(self):
        import apps.organizations.signals  # noqa
