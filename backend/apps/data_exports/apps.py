from django.apps import AppConfig


class DataExportsConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"  # pyright: ignore[reportAssignmentType]
    )
    name = "apps.data_exports"
    label = "data_exports"

    def ready(self):
        from .datasets import register_default_datasets

        register_default_datasets()
