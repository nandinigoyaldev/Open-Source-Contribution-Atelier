import uuid
from django.core.management.base import BaseCommand
from apps.sandbox.models import LicenseScenario, DependencyDiff


class Command(BaseCommand):
    help = "Seeds initial License Scenarios."

    def handle(self, *args, **options):
        self.stdout.write("Seeding License Scenarios...")

        # Scenario 1: GPL in MIT
        scenario1, created = LicenseScenario.objects.get_or_create(
            title="Sneaky GPL in an MIT Project",
            defaults={
                "description": "An ambitious contributor has submitted a PR that adds a new charting library to your MIT-licensed React dashboard.",
                "base_project_license": "MIT",
                "difficulty": 2,
            },
        )

        if not created:
            self.stdout.write("Scenario 1 already exists, skipping...")
        else:
            DependencyDiff.objects.create(
                scenario=scenario1,
                package_name="super-charts",
                package_license="GPLv3",
                diff_text='+ "super-charts": "^1.0.0"',
                is_violation=True,
                explanation="GPLv3 is a strong copyleft license. If you include it in your MIT project, your entire project must be distributed under GPLv3, which violates your current MIT licensing strategy.",
            )
            DependencyDiff.objects.create(
                scenario=scenario1,
                package_name="lodash",
                package_license="MIT",
                diff_text='+ "lodash": "^4.17.21"',
                is_violation=False,
                explanation="Lodash is MIT licensed and fully compatible.",
            )

        # Scenario 2: Commercial license
        scenario2, created = LicenseScenario.objects.get_or_create(
            title="Enterprise Component Library",
            defaults={
                "description": "A PR adds a beautifully designed data grid component to your open-source project.",
                "base_project_license": "Apache 2.0",
                "difficulty": 1,
            },
        )

        if created:
            DependencyDiff.objects.create(
                scenario=scenario2,
                package_name="ag-grid-enterprise",
                package_license="Commercial",
                diff_text='+ "ag-grid-enterprise": "^30.0.0"',
                is_violation=True,
                explanation="Commercial licenses cannot be used in open-source projects without a paid license, and they restrict the freedom of your users.",
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded License Scenarios."))
