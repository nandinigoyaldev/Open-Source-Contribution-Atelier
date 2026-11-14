from django.core.management.base import BaseCommand

from apps.search.durable import replay_failure
from apps.search.meili_client import get_meili_index
from apps.search.models import SearchIndexFailure
from apps.search.utils import bump_search_cache_version


class Command(BaseCommand):
    help = "Replays Meilisearch writes recorded in SearchIndexFailure (safe to re-run)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List open failures without contacting Meilisearch.",
        )

    def handle(self, *args, **options):
        failures = list(SearchIndexFailure.objects.all())
        if not failures:
            self.stdout.write("No open search index failures.")
            return

        if options["dry_run"]:
            for failure in failures:
                self.stdout.write(
                    f"{failure.operation} {failure.document_id} "
                    f"attempts={failure.attempts} last_error={failure.last_error}"
                )
            self.stdout.write(f"{len(failures)} open failure(s).")
            return

        index = get_meili_index()
        if not index:
            self.stdout.write(self.style.ERROR("Meilisearch client unavailable."))
            return

        resolved = sum(1 for failure in failures if replay_failure(failure, index))
        remaining = len(failures) - resolved
        if resolved:
            bump_search_cache_version()
        if remaining:
            self.stdout.write(
                self.style.WARNING(
                    f"Replayed {resolved}, {remaining} still failing (see admin)."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Replayed {resolved} failure(s)."))
