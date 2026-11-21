from rest_framework import serializers

from .models import (
    Exercise,
    LearningPath,
    Lesson,
    LessonDraft,
    LessonFeedback,
    ModuleDraft,
    Organization,
    QuizDraft,
)


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


class LessonVersionSerializer(CamelCaseModelSerializer):
    author_name = serializers.CharField(
        source="author.username", read_only=True, default=None
    )
    published_by_name = serializers.CharField(
        source="published_by.username", read_only=True, default=None
    )
    restored_from_number = serializers.IntegerField(
        source="restored_from.number", read_only=True, default=None
    )

    class Meta:
        from .models import LessonVersion

        model = LessonVersion
        fields = [
            "id",
            "number",
            "status",
            "title",
            "summary",
            "content",
            "note",
            "author_name",
            "restored_from_number",
            "published_at",
            "published_by_name",
            "created_at",
        ]


class LessonDraftRevisionSerializer(serializers.Serializer):
    """Input for a new draft revision; title and summary default to the lesson's."""

    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField()
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class LessonSerializer(CamelCaseModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)
    prerequisites = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="slug"
    )
    reading_time = serializers.ReadOnlyField()

    class Meta:
        model = Lesson
        fields = "__all__"


class LessonSearchSerializer(CamelCaseModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)
    prerequisites = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="slug"
    )
    reading_time = serializers.ReadOnlyField()

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


class LessonFeedbackSerializer(CamelCaseModelSerializer):
    """Serializer for lesson feedback with star ratings and comments."""

    class Meta:
        model = LessonFeedback
        fields = ["id", "lesson", "rating", "comment", "created_at", "updated_at"]
        read_only_fields = [
            "id",
            "lesson",
            "created_at",
            "updated_at",
        ]


class LessonFeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating lesson feedback."""

    lesson = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = LessonFeedback
        fields = ["lesson", "rating", "comment"]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5 stars.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        lesson_slug = self.context.get("lesson_slug")

        if not lesson_slug:
            raise serializers.ValidationError({"lesson": "Lesson context is required."})

        if LessonFeedback.objects.filter(
            user=user,
            lesson__slug=lesson_slug,
            is_deleted=False,
        ).exists():
            raise serializers.ValidationError(
                "You have already submitted feedback for this lesson."
            )

        return attrs


class LessonFeedbackMetricsSerializer(serializers.Serializer):
    """Serializer for aggregated feedback metrics for a lesson."""

    lesson_slug = serializers.CharField()
    average_rating = serializers.FloatField()
    total_count = serializers.IntegerField()
    rating_distribution = serializers.DictField(child=serializers.IntegerField())

    def to_representation(self, instance):
        return camelize(super().to_representation(instance))


class QuizDraftSerializer(CamelCaseModelSerializer):
    class Meta:
        model = QuizDraft
        fields = "__all__"


class LessonDraftSerializer(CamelCaseModelSerializer):
    quizzes = QuizDraftSerializer(many=True, read_only=True)

    class Meta:
        model = LessonDraft
        fields = "__all__"


class ModuleDraftSerializer(CamelCaseModelSerializer):
    lessons = LessonDraftSerializer(many=True, read_only=True)

    class Meta:
        model = ModuleDraft
        fields = "__all__"


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.rbac.models import Role

        model = Role
        fields = ["id", "name", "description"]


class LearningPathSerializer(CamelCaseModelSerializer):
    required_roles_details = RoleSerializer(
        source="required_roles", many=True, read_only=True
    )
    has_access = serializers.SerializerMethodField()

    class Meta:
        model = LearningPath
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "is_published",
            "required_roles",
            "required_roles_details",
            "has_access",
            "created_at",
            "updated_at",
        ]

    def get_has_access(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return obj.has_access(user)
