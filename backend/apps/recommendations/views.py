from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Recommendation
from .serializers import RecommendationSerializer
from .engine import RecommendationEngine

class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recommendation.objects.filter(
            user=self.request.user, is_dismissed=False
        ).order_by("-priority_score", "-created_at")

class GenerateRecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        engine = RecommendationEngine(request.user)
        engine.generate_recommendations()
        return Response({"status": "success"}, status=status.HTTP_200_OK)

class DismissRecommendationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            recommendation = Recommendation.objects.get(pk=pk, user=request.user)
            recommendation.is_dismissed = True
            recommendation.save()
            return Response({"status": "dismissed"}, status=status.HTTP_200_OK)
        except Recommendation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
