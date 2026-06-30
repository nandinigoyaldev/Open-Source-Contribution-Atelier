import graphene
from graphene_django.types import DjangoObjectType

from .models import Exercise, Lesson, Organization



class OrganizationType(DjangoObjectType):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "logo_url",
            "popularity_score",
            "date_added",
        )


class ExerciseType(DjangoObjectType):
    class Meta:
        model = Exercise
        fields = (
            "id",
            "lesson",
            "title",
            "prompt",
            "expected_command",
            "explanation",
            "points",
        )


class LessonType(DjangoObjectType):
    class Meta:
        model = Lesson
        fields = (
            "id",
            "organization",
            "difficulty",
            "title",
            "slug",
            "summary",
            "content",
            "learning_objectives",
            "tips",
            "category",
            "estimated_minutes",
            "order",
        )

    exercises = graphene.List(ExerciseType)

    def resolve_exercises(self, info):
        return self.exercises.all()


class Query(graphene.ObjectType):
    all_lessons = graphene.List(LessonType)
    lesson_by_slug = graphene.Field(LessonType, slug=graphene.String(required=True))
    all_organizations = graphene.List(OrganizationType)

    def resolve_all_lessons(root, info):
        # Prevent N+1 queries when fetching lessons and their exercises
        queryset = Lesson.objects.prefetch_related("exercises")
        if info.context.user.is_authenticated and hasattr(
            info.context.user, "organization"
        ):
            queryset = queryset.filter(organization=info.context.user.organization)
        return queryset.all()

    def resolve_lesson_by_slug(root, info, slug):
        try:
            lesson = Lesson.objects.prefetch_related("exercises").get(slug=slug)
            if info.context.user.is_authenticated and hasattr(
                info.context.user, "organization"
            ):
                if lesson.organization_id != info.context.user.organization_id:
                    return None
            return lesson
        except Lesson.DoesNotExist:
            return None

    def resolve_all_organizations(root, info):
        return Organization.objects.all()
