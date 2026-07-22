from rest_framework import serializers
from .models import ExpertiseDomain, MaintainerExpertise, IssueRouting, RoutingMetric


class ExpertiseDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertiseDomain
        fields = "__all__"


class MaintainerExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintainerExpertise
        fields = "__all__"


class IssueRoutingSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueRouting
        fields = "__all__"


class RoutingMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingMetric
        fields = "__all__"
