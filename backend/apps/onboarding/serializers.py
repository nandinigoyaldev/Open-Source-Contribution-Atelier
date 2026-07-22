from rest_framework import serializers
from .models import OnboardingJourney, JourneyEvent, OnboardingNudge, OnboardingMetric

class OnboardingJourneySerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingJourney
        fields = '__all__'

class JourneyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = JourneyEvent
        fields = '__all__'

class OnboardingNudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingNudge
        fields = '__all__'

class OnboardingMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingMetric
        fields = '__all__'

