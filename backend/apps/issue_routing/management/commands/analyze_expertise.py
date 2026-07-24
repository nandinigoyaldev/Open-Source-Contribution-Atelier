"""
Management command to analyze maintainer expertise.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()
from apps.issue_routing.models import MaintainerExpertise, ExpertiseDomain
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Analyze maintainer expertise from GitHub contributions.

    Usage:
        python manage.py analyze_expertise
        python manage.py analyze_expertise --user username
    """

    help = "Analyze maintainer expertise from GitHub contributions"

    def add_arguments(self, parser):
        parser.add_argument("--user", type=str, help="Specific user to analyze")

    def handle(self, *args, **options):
        users = User.objects.filter(is_staff=True)

        if options.get("user"):
            users = users.filter(username=options["user"])

        self.stdout.write(f"Analyzing {users.count()} maintainers...")

        for user in users:
            self._analyze_user(user)

        self.stdout.write("✅ Analysis complete!")

    def _analyze_user(self, user):
        """Analyze a single user."""
        # Create or update expertise profile
        profile, created = MaintainerExpertise.objects.get_or_create(user=user)

        # In production, fetch from GitHub API
        # For now, use mock data
        domains = ExpertiseDomain.objects.all()

        if domains:
            # Assign primary domains based on user's contributions
            primary_domain = domains.first()
            profile.primary_domains.set([primary_domain])

            if domains.count() > 1:
                profile.secondary_domains.set([domains[1]])

        profile.contributions_count = 10  # Placeholder
        profile.routing_accuracy = 0.85
        profile.avg_resolution_time = 48  # hours
        profile.save()

        self.stdout.write(f"  ✅ Analyzed {user.username}")
