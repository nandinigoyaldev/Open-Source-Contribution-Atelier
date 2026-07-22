from rest_framework import serializers
from .models import ContributorActivity, BurnoutSignal, Intervention, BurnoutMetric

class ContributorActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributorActivity
        fields = '__all__'

class BurnoutSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BurnoutSignal
        fields = '__all__'

class InterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = '__all__'

class BurnoutMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = BurnoutMetric
        fields = '__all__'

