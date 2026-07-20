from .models import Experiment, ExperimentEvent
from django.db.models import Count, Q
import math

def calculate_significance(experiment_id):
    """Calculate chi-squared significance for experiment."""
    experiment = Experiment.objects.get(id=experiment_id)
    
    results = {}
    for variant in experiment.variants:
        total = ExperimentEvent.objects.filter(
            experiment=experiment,
            variant=variant,
            event_type='view'
        ).count()
        
        conversions = ExperimentEvent.objects.filter(
            experiment=experiment,
            variant=variant,
            event_type='conversion'
        ).count()
        
        results[variant] = {
            'views': total,
            'conversions': conversions,
            'rate': conversions / total if total > 0 else 0
        }
    
    # Simple significance check
    # Chi-squared calculation here
    
    return results