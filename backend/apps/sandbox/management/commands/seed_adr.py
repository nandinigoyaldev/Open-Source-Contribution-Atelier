import uuid
from django.core.management.base import BaseCommand
from apps.sandbox.models import ADRScenario, ADROption


class Command(BaseCommand):
    help = "Seeds initial ADR Scenarios."

    def handle(self, *args, **options):
        self.stdout.write("Seeding ADR Scenarios...")

        scenario, created = ADRScenario.objects.get_or_create(
            title="Choosing a Caching Layer",
            defaults={
                "context": "Our monolithic application is experiencing slow response times on the homepage because we compute a complex leaderboard on every request. The leaderboard only needs to be updated every 5 minutes. We need to introduce a caching layer.",
                "constraints": "The solution must be horizontally scalable, support complex data structures (like sorted sets for leaderboards), and have minimal latency.",
            },
        )

        if not created:
            self.stdout.write("Scenario already exists, skipping...")
        else:
            ADROption.objects.create(
                scenario=scenario,
                title="Use Memcached",
                pros="Extremely fast, simple key-value store, multi-threaded.",
                cons="Does not support complex data structures like sorted sets out-of-the-box. Eviction policies are simpler.",
                is_optimal=False,
            )
            ADROption.objects.create(
                scenario=scenario,
                title="Use Redis",
                pros="Supports complex data structures (sorted sets are perfect for leaderboards), persistent, supports replication and clustering.",
                cons="Single-threaded (though generally not an issue for this workload), higher memory overhead than Memcached.",
                is_optimal=True,
            )
            ADROption.objects.create(
                scenario=scenario,
                title="Use Database Caching (PostgreSQL Materialized Views)",
                pros="No new infrastructure needed. Data remains in the SQL ecosystem.",
                cons="Materialized views take time to refresh, and querying them still adds load to the primary database. Not as fast as in-memory stores.",
                is_optimal=False,
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded ADR Scenarios."))
