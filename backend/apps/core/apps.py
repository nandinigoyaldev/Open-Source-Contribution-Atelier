from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        import apps.core.checks  # noqa
        
        from django.db.backends.signals import connection_created
        
        def configure_sqlite(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode = WAL;')
                cursor.execute('PRAGMA synchronous = NORMAL;')
                cursor.execute('PRAGMA cache_size = -64000;')
                cursor.execute('PRAGMA busy_timeout = 5000;')
                
        connection_created.connect(configure_sqlite)

        try:
            from django_q.models import Schedule

            # Create a daily schedule to run the GDPR purge pipeline
            Schedule.objects.get_or_create(
                func="apps.core.tasks.purge_expired_soft_deleted_records",
                defaults={
                    "schedule_type": Schedule.DAILY,
                    "repeats": -1,  # Infinite repeats
                },
            )
        except Exception:
            # Table might not be migrated yet or django_q not installed
            pass
