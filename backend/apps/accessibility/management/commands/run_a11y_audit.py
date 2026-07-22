from django.core.management.base import BaseCommand
import subprocess
import os
import json


class Command(BaseCommand):
    help = "Runs an automated accessibility audit using Playwright and axe-core"

    def handle(self, *args, **options):
        self.stdout.write("Running accessibility audit...")

        frontend_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                )
            ),
            "frontend",
        )

        try:
            # We trigger the playwright script from the frontend dir
            result = subprocess.run(
                ["npm", "run", "test:e2e", "--", "e2e/a11y.spec.ts"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS("Accessibility audit passed successfully.")
                )
            else:
                self.stdout.write(
                    self.style.ERROR("Accessibility audit failed. Found violations.")
                )
                self.stdout.write(result.stdout)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error running audit: {str(e)}"))
