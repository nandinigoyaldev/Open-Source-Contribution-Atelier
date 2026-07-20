from django.utils.deprecation import MiddlewareMixin
from .models import Experiment, ExperimentAssignment
import random

class ExperimentMiddleware(MiddlewareMixin):
    """Assigns users to experiment variants."""
    
    def process_request(self, request):
        if not request.user.is_authenticated:
            return
        
        # Get active experiments
        experiments = Experiment.objects.filter(status='active')
        
        for experiment in experiments:
            # Check if already assigned
            if ExperimentAssignment.objects.filter(
                experiment=experiment,
                user=request.user
            ).exists():
                continue
            
            # Traffic allocation
            if random.random() > experiment.traffic_allocation:
                continue
            
            # Assign variant
            variants = experiment.variants
            variant = random.choice(variants)
            
            ExperimentAssignment.objects.create(
                experiment=experiment,
                user=request.user,
                variant=variant
            )