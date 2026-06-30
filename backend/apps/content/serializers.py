from rest_framework import serializers

from .models import Exercise, Lesson


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"


class LessonSerializer(serializers.ModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = "__all__"
