from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime, parse_date
from django.apps import apps
from django.db import transaction
from django.utils.timezone import make_aware
from datetime import datetime, time
from apps.audit.models import AuditEvent


class Command(BaseCommand):
    help = "Replay audit events to rebuild model state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--from",
            dest="from_date",
            type=str,
            required=True,
            help="Start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        )
        parser.add_argument(
            "--to",
            dest="to_date",
            type=str,
            required=True,
            help="End date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        )
        parser.add_argument(
            "--resource-type",
            type=str,
            required=True,
            help="Resource model type (e.g., 'content.lesson' or just 'lesson')",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without committing changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        from_str = options["from_date"]
        to_str = options["to_date"]
        res_type = options["resource_type"]

        # Parse dates
        start_dt = self._parse_datetime_or_date(from_str, is_start=True)
        end_dt = self._parse_datetime_or_date(to_str, is_start=False)

        # Resolve Model
        model_cls = self._resolve_model(res_type)

        # Query events chronological (oldest first for replay)
        events = AuditEvent.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        ).order_by("created_at")

        # Filter by resource type
        if "." in res_type:
            events = events.filter(resource_type__iexact=res_type)
        else:
            events = events.filter(resource_type__endswith=f".{res_type}")

        count = events.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {count} events for {res_type} from {start_dt} to {end_dt}."
            )
        )

        if count == 0:
            return

        # Execute replay inside a transaction
        try:
            with transaction.atomic():
                for event in events:
                    self._replay_event(model_cls, event, dry_run)

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING("Dry run enabled. Rolling back transaction.")
                    )
                    transaction.set_rollback(True)
                else:
                    self.stdout.write(
                        self.style.SUCCESS("Replay committed successfully.")
                    )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Replay failed: {str(e)}"))
            raise CommandError("Replay execution failed.") from e

    def _parse_datetime_or_date(self, val: str, is_start: bool) -> datetime:
        dt = parse_datetime(val)
        if dt:
            if dt.tzinfo is None:
                dt = make_aware(dt)
            return dt

        d = parse_date(val)
        if d:
            t = time.min if is_start else time.max
            dt = datetime.combine(d, t)
            return make_aware(dt)

        raise CommandError(
            f"Invalid date/datetime format: '{val}'. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."
        )

    def _resolve_model(self, res_type: str):
        if "." in res_type:
            app_label, model_name = res_type.split(".", 1)
            try:
                return apps.get_model(app_label, model_name)
            except LookupError as e:
                raise CommandError(f"Model '{res_type}' not found.") from e
        else:
            # Search for the model name across all apps
            found_models = []
            for config in apps.get_app_configs():
                for model in config.get_models():
                    if model.__name__.lower() == res_type.lower():
                        found_models.append(model)
            if not found_models:
                raise CommandError(f"No model found matching name '{res_type}'.")
            if len(found_models) > 1:
                options = ", ".join(
                    f"{m._meta.app_label}.{m.__name__}" for m in found_models
                )
                raise CommandError(
                    f"Ambiguous model name '{res_type}'. Matches: {options}. Use app_label.model_name format."
                )
            return found_models[0]

    def _replay_event(self, model_cls, event: AuditEvent, dry_run: bool):
        pk = event.resource_id
        action = event.action
        snapshot = event.after or event.before

        if not snapshot:
            self.stdout.write(
                f"Skipping event {event.id} ({action}): No snapshot data found."
            )
            return

        self.stdout.write(
            f"Replaying {event.resource_type}#{pk} ({action}) from {event.created_at}..."
        )

        # Find or construct the instance
        manager = model_cls.objects
        if hasattr(model_cls, "all_objects"):
            # Handle SoftDeleteModels if applicable
            manager = model_cls.all_objects

        instance = None
        try:
            instance = manager.get(pk=pk)
        except model_cls.DoesNotExist:
            pass

        # Separate many-to-many fields from snapshot
        non_m2m_snapshot = {}
        m2m_snapshot = {}
        for field_name, value in snapshot.items():
            try:
                field = model_cls._meta.get_field(field_name)
                if field.many_to_many:
                    m2m_snapshot[field_name] = value
                else:
                    non_m2m_snapshot[field_name] = value
            except Exception:
                non_m2m_snapshot[field_name] = value

        if action == AuditEvent.ACTION_CREATED:
            if instance:
                self.stdout.write(
                    f"  Warning: instance {pk} already exists for 'created' event. Updating fields instead."
                )
                self._update_fields(instance, non_m2m_snapshot)
                if not dry_run:
                    self._update_m2m_fields(instance, m2m_snapshot)
            else:
                instance = model_cls(**non_m2m_snapshot)
                # Ensure the primary key matches exactly
                instance.pk = pk
                if not dry_run:
                    instance.save()
                    self._update_m2m_fields(instance, m2m_snapshot)
        elif action == AuditEvent.ACTION_UPDATED:
            if not instance:
                self.stdout.write(
                    f"  Warning: instance {pk} does not exist for 'updated' event. Recreating instance."
                )
                instance = model_cls(**non_m2m_snapshot)
                instance.pk = pk
                if not dry_run:
                    instance.save()
                    self._update_m2m_fields(instance, m2m_snapshot)
            else:
                self._update_fields(instance, non_m2m_snapshot)
                if not dry_run:
                    instance.save()
                    self._update_m2m_fields(instance, m2m_snapshot)
        elif action == AuditEvent.ACTION_DELETED:
            if instance:
                if not dry_run:
                    instance.delete()
            else:
                self.stdout.write(f"  Instance {pk} already deleted/does not exist.")

    def _update_fields(self, instance, snapshot: dict):
        for field, value in snapshot.items():
            # Skip updating primary key
            if field == instance._meta.pk.name:
                continue
            # Make sure field exists on model
            if hasattr(instance, field):
                setattr(instance, field, value)

    def _update_m2m_fields(self, instance, m2m_snapshot: dict):
        for field_name, value in m2m_snapshot.items():
            if hasattr(instance, field_name) and isinstance(value, list):
                try:
                    getattr(instance, field_name).set(value)
                except Exception as e:
                    self.stdout.write(
                        f"  Warning: failed to set many-to-many field '{field_name}': {str(e)}"
                    )
