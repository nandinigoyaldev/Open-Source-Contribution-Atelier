from rest_framework import viewsets, views, response, permissions, generics, filters
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity

from .models import Lesson, Organization
from .serializers import LessonSerializer, OrganizationSerializer
from apps.challenges.models import Challenge
from apps.challenges.serializers import ChallengeSerializer
from apps.progress.models import LessonProgress
from apps.search.models import SearchDocument

# --- Helper Functions ---
def get_active_lessons():
    lessons = cache.get("active_lessons_list")
    if lessons is None:
        lessons = list(Lesson.objects.prefetch_related("exercises").all())
        cache.set("active_lessons_list", lessons, 60 * 60 * 24)
    return lessons

# --- Existing Views ---
class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonSerializer

    def list(self, request, *args, **kwargs):
        lessons = get_active_lessons()
        serializer = self.get_serializer(lessons, many=True)
        return response.Response(serializer.data)

class SearchView(views.APIView):
    def get(self, request):
        query = request.GET.get("q", "")
        if not query:
            return response.Response({"lessons": [], "challenges": []})
        search_query = SearchQuery(query)
        lesson_ct = ContentType.objects.get_for_model(Lesson)
        challenge_ct = ContentType.objects.get_for_model(Challenge)
        
        def get_fts_objects(model_class, content_type):
            docs = SearchDocument.objects.filter(
                content_type=content_type, search_vector=search_query
            ).annotate(rank=SearchRank('search_vector', search_query)).order_by('-rank')[:50]
            
            if not docs.exists():
                docs = SearchDocument.objects.filter(
                    content_type=content_type
                ).annotate(similarity=TrigramSimilarity('title', query)).filter(similarity__gt=0.3).order_by('-similarity')[:50]
                
            object_ids = [doc.object_id for doc in docs]
            if not object_ids:
                return []
                
            objects = model_class.objects.filter(id__in=object_ids, organization=request.user.organization)
            # Sort them in the exact order returned by FTS
            ordered_objects = sorted(objects, key=lambda x: object_ids.index(x.id))
            return ordered_objects

        lessons = get_fts_objects(Lesson, lesson_ct)
        challenges = get_fts_objects(Challenge, challenge_ct)
        
        return response.Response({
            "lessons": LessonSerializer(lessons, many=True).data,
            "challenges": ChallengeSerializer(challenges, many=True).data
        })

class RoadmapView(views.APIView):
    """Return ordered curriculum with optional per-user completion state."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        lessons = get_active_lessons()

        progress_by_slug = {}

        if request.user and request.user.is_authenticated:
            progress_rows = (
                LessonProgress.objects.filter(
                    user=request.user,
                    organization=request.user.organization,
                    lesson__in=lessons,
                ).select_related("lesson")
            )

            progress_by_slug = {
                p.lesson.slug: p for p in progress_rows
            }

        track = []
        completed_count = 0

        for lesson in lessons:
            user_progress = progress_by_slug.get(lesson.slug)
            completed = bool(user_progress and user_progress.completed)
            score = int(user_progress.score) if user_progress else 0

            if completed:
                completed_count += 1

            track.append(
                {
                    "id": lesson.id,
                    "slug": lesson.slug,
                    "title": lesson.title,
                    "summary": lesson.summary,
                    "difficulty": lesson.difficulty,
                    "estimated_minutes": lesson.estimated_minutes,
                    "order": lesson.order,
                    "exercise_count": lesson.exercises.count(),
                    "completed": completed,
                    "score": score,
                }
            )

        return response.Response(
            {
                "track": track,
                "stats": {
                    "total_lessons": len(track),
                    "completed_lessons": completed_count,
                },
            }
        )

# --- New: Organization View ---
class OrganizationListView(generics.ListAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['name', 'date_added', 'popularity_score']
    ordering = ['-popularity_score']
