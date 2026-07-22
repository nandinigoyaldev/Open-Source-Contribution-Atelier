from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import OnboardingJourney, JourneyEvent, OnboardingNudge, OnboardingMetric
from .serializers import OnboardingJourneySerializer, JourneyEventSerializer, OnboardingNudgeSerializer, OnboardingMetricSerializer

class OnboardingJourneyViewSet(viewsets.ModelViewSet):
    queryset = OnboardingJourney.objects.all()
    serializer_class = OnboardingJourneySerializer
    permission_classes = [IsAuthenticated]

class JourneyEventViewSet(viewsets.ModelViewSet):
    queryset = JourneyEvent.objects.all()
    serializer_class = JourneyEventSerializer
    permission_classes = [IsAuthenticated]

class OnboardingNudgeViewSet(viewsets.ModelViewSet):
    queryset = OnboardingNudge.objects.all()
    serializer_class = OnboardingNudgeSerializer
    permission_classes = [IsAuthenticated]

class OnboardingMetricViewSet(viewsets.ModelViewSet):
    queryset = OnboardingMetric.objects.all()
    serializer_class = OnboardingMetricSerializer
    permission_classes = [IsAuthenticated]

