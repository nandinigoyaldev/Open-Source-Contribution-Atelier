from rest_framework import serializers
from .models import Experiment, ExperimentAssignment, ExperimentEvent

class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = '__all__'

class ExperimentAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentAssignment
        fields = '__all__'

class ExperimentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentEvent
        fields = '__all__'

