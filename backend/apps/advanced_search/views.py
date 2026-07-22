from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import SearchEmbedding, UserSearchProfile, SearchAnalytics
from .serializers import (
    SearchEmbeddingSerializer,
    UserSearchProfileSerializer,
    SearchAnalyticsSerializer,
)


class SearchEmbeddingViewSet(viewsets.ModelViewSet):
    queryset = SearchEmbedding.objects.all()
    serializer_class = SearchEmbeddingSerializer
    permission_classes = [IsAuthenticated]


class UserSearchProfileViewSet(viewsets.ModelViewSet):
    queryset = UserSearchProfile.objects.all()
    serializer_class = UserSearchProfileSerializer
    permission_classes = [IsAuthenticated]


class SearchAnalyticsViewSet(viewsets.ModelViewSet):
    queryset = SearchAnalytics.objects.all()
    serializer_class = SearchAnalyticsSerializer
    permission_classes = [IsAuthenticated]
