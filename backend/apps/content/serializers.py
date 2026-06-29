from rest_framework import serializers

from .models import Exercise, Lesson, Organization


def to_camel_case(snake_str):
    if not snake_str or "_" not in snake_str:
        return snake_str
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def camelize(data):
    if isinstance(data, dict):
        return {to_camel_case(k): camelize(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [camelize(i) for i in data]
    return data


class CamelCaseModelSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        return camelize(ret)


class ExerciseSerializer(CamelCaseModelSerializer):
    class Meta:
        model = Exercise
        fields = "__all__"


class LessonSerializer(CamelCaseModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)
    prerequisites = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="slug"
    )

    class Meta:
        model = Lesson
        fields = "__all__"


class LessonSearchSerializer(CamelCaseModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)
    prerequisites = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="slug"
    )

    class Meta:
        model = Lesson
        exclude = ["embedding"]


class OrganizationSerializer(CamelCaseModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo_url",
            "date_added",
            "popularity_score",
        ]
