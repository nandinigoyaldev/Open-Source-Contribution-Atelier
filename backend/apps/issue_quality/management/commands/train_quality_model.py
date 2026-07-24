"""
Management command to train quality model.
"""

from django.core.management.base import BaseCommand
from apps.issue_quality.models import WontfixPattern
import json
import os


class Command(BaseCommand):
    """
    Train quality model with WONTFIX patterns.

    Usage:
        python manage.py train_quality_model
        python manage.py train_quality_model --file patterns.json
    """

    help = "Train quality model with WONTFIX patterns"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="JSON file with WONTFIX patterns")

    def handle(self, *args, **options):
        patterns_file = options.get("file")

        if patterns_file:
            self._load_patterns_from_file(patterns_file)
        else:
            self._load_default_patterns()

        self.stdout.write(
            f"✅ Loaded {WontfixPattern.objects.count()} WONTFIX patterns"
        )

    def _load_patterns_from_file(self, filepath):
        """Load patterns from JSON file."""
        if not os.path.exists(filepath):
            self.stdout.write(f"❌ File {filepath} not found")
            return

        with open(filepath, "r") as f:
            patterns = json.load(f)

        for pattern in patterns:
            WontfixPattern.objects.get_or_create(
                pattern=pattern["pattern"],
                defaults={
                    "category": pattern["category"],
                    "frequency": pattern.get("frequency", 0),
                },
            )

    def _load_default_patterns(self):
        """Load default WONTFIX patterns."""
        default_patterns = [
            {"pattern": "works on my machine", "category": "User-Specific"},
            {"pattern": "can't reproduce", "category": "No Discussion"},
            {"pattern": "duplicate of", "category": "Duplicate"},
            {"pattern": "external library", "category": "External Project"},
            {"pattern": "not a bug", "category": "No Discussion"},
            {"pattern": "wontfix", "category": "WONTFIX"},
            {"pattern": "invalid", "category": "No Discussion"},
            {"pattern": "by design", "category": "No Discussion"},
            {"pattern": "use stackoverflow", "category": "External Project"},
            {"pattern": "already fixed", "category": "Duplicate"},
            {"pattern": "needs more info", "category": "No Discussion"},
        ]

        for pattern in default_patterns:
            WontfixPattern.objects.get_or_create(
                pattern=pattern["pattern"], defaults={"category": pattern["category"]}
            )
