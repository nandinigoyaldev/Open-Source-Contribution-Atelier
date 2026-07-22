import logging

from django.utils.deprecation import MiddlewareMixin
from .models import Experiment, ExperimentAssignment
import random

logger = logging.getLogger(__name__)


class ExperimentMiddleware(MiddlewareMixin):
    """Assigns users to experiment variants."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            return

        experiments = Experiment.objects.filter(status="active")
        if not experiments:
            return

        # Bulk-fetch which of these active experiments the user is already
        # assigned to in a single query, instead of one .exists() query
        # per experiment on every request.
        already_assigned_ids = set(
            ExperimentAssignment.objects.filter(
                experiment__in=experiments, user=request.user
            ).values_list("experiment_id", flat=True)
        )

        for experiment in experiments:
            if experiment.id in already_assigned_ids:
                continue

            try:
                traffic_allocation = experiment.traffic_allocation
                variants = experiment.variants

                if not variants:
                    logger.warning(
                        "Skipping experiment assignment: experiment %s has no variants",
                        experiment.id,
                    )
                    continue

                if traffic_allocation is None:
                    logger.warning(
                        "Skipping experiment assignment: experiment %s has no traffic_allocation",
                        experiment.id,
                    )
                    continue

                if random.random() > traffic_allocation:
                    continue

                variant = random.choice(variants)

                ExperimentAssignment.objects.create(
                    experiment=experiment, user=request.user, variant=variant
                )
            except Exception as e:
                # A single misconfigured experiment should never break the
                # request for an unrelated user.
                logger.error(
                    "Failed to assign user %s to experiment %s: %s",
                    request.user.id,
                    experiment.id,
                    e,
                )
                continue
