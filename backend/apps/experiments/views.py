from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Experiment, ExperimentAssignment, ExperimentEvent
from .serializers import ExperimentSerializer, ExperimentAssignmentSerializer, ExperimentEventSerializer

class ExperimentViewSet(viewsets.ModelViewSet):
    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer
    permission_classes = [IsAuthenticated]

class ExperimentAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ExperimentAssignment.objects.all()
    serializer_class = ExperimentAssignmentSerializer
    permission_classes = [IsAuthenticated]

class ExperimentEventViewSet(viewsets.ModelViewSet):
    queryset = ExperimentEvent.objects.all()
    serializer_class = ExperimentEventSerializer
    permission_classes = [IsAuthenticated]

