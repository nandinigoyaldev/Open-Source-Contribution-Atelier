from .models import FeatureFlag


def feature_flags(request):
    return {"feature_flags": FeatureFlag.objects.all_flags()}
