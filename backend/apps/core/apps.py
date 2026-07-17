from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        import apps.core.checks  # noqa
        import apps.core.celery_signals  # noqa

        from django.db.backends.signals import connection_created

        def configure_sqlite(sender, connection, **kwargs):
            if connection.vendor == "sqlite":
                cursor = connection.cursor()
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("PRAGMA synchronous = NORMAL;")
                cursor.execute("PRAGMA cache_size = -64000;")
                cursor.execute("PRAGMA busy_timeout = 5000;")

        connection_created.connect(configure_sqlite)

        try:
            import apps.core.signals  # noqa: F401
            import apps.core.cache.signals  # noqa: F401
        except ImportError:
            pass

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

            # Daily database backup
            Schedule.objects.get_or_create(
                name="db-backup-daily",
                defaults={
                    "func": "apps.core.tasks.backup_database",
                    "schedule_type": Schedule.DAILY,
                    "repeats": -1,
                },
            )

            # Weekly backup pruning (retention enforcement)
            Schedule.objects.get_or_create(
                name="db-backup-prune-weekly",
                defaults={
                    "func": "apps.core.tasks.prune_old_backups",
                    "schedule_type": Schedule.WEEKLY,
                    "repeats": -1,
                },
            )

            Schedule.objects.get_or_create(
                name="audit-log-archive-monthly",
                defaults={
                    "func": "apps.core.tasks.archive_audit_logs",
                    "schedule_type": Schedule.MONTHLY,
                    "repeats": -1,
                },
            )

            # Daily domain audit events archival to cold storage/archives
            Schedule.objects.get_or_create(
                name="audit-events-archive-daily",
                defaults={
                    "func": "apps.audit.tasks.archive_audit_events",
                    "schedule_type": Schedule.DAILY,
                    "repeats": -1,
                },
            )
        except Exception:
            # Table might not be migrated yet or django_q not installed
            pass
