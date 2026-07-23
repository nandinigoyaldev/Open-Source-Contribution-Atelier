from datetime import datetime, timedelta, timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MaintainerWorkloadProfile, RepoHealthScore
from .serializers import MaintainerWorkloadProfileSerializer, RepoHealthScoreSerializer
from .services import analyze_repository, BurnoutAnalyzer


class AnalyzeRepositoryView(APIView):
    """
    POST /api/project-health/analyze/
    Body: { "repo_url": "https://github.com/django/django" }

    Returns a full health analysis of the requested GitHub repository.
    Results are cached for CACHE_TTL_HOURS to avoid excessive API calls.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        repo_url = request.data.get("repo_url", "").strip()

        if not repo_url:
            return Response(
                {"error": "repo_url is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not repo_url.startswith("https://github.com/"):
            return Response(
                {
                    "error": "Only GitHub repository URLs are supported (https://github.com/...)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return cached result if fresh
        existing = RepoHealthScore.objects.filter(repo_url=repo_url).first()
        if existing:
            ttl = timedelta(hours=RepoHealthScore.CACHE_TTL_HOURS)
            if datetime.now(tz=timezone.utc) - existing.updated_at < ttl:
                return Response(RepoHealthScoreSerializer(existing).data)

        # Run fresh analysis
        try:
            metrics = analyze_repository(repo_url)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to analyze repository: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Upsert the result
        obj, _ = RepoHealthScore.objects.update_or_create(
            repo_url=repo_url,
            defaults={**metrics, "analyzed_by": request.user},
        )

        return Response(
            RepoHealthScoreSerializer(obj).data,
            status=status.HTTP_200_OK,
        )


class RepoHealthHistoryView(APIView):
    """
    GET /api/project-health/history/
    Returns the list of repositories the authenticated user has previously analyzed.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        analyses = RepoHealthScore.objects.filter(analyzed_by=request.user).order_by(
            "-updated_at"
        )[:20]
        return Response(RepoHealthScoreSerializer(analyses, many=True).data)


class MaintainerWorkloadView(APIView):
    """
    GET /api/project-health/burnout/
    Returns the workload profile and burnout risk score for the authenticated user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = MaintainerWorkloadProfile.objects.get_or_create(user=request.user)
        # Recompute score on fetch
        BurnoutAnalyzer.compute_risk_score(profile)
        return Response(MaintainerWorkloadProfileSerializer(profile).data)

    def patch(self, request):
        """
        PATCH /api/project-health/burnout/
        Allows updating workload metrics (active_prs_assigned, etc)
        """
        profile, _ = MaintainerWorkloadProfile.objects.get_or_create(user=request.user)
        serializer = MaintainerWorkloadProfileSerializer(
            profile, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            BurnoutAnalyzer.compute_risk_score(profile)
            return Response(MaintainerWorkloadProfileSerializer(profile).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
