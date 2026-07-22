from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import FeatureRequest, Vote, Comment, StatusHistory, RoadmapMilestone
from .serializers import (
    FeatureRequestSerializer,
    VoteSerializer,
    CommentSerializer,
    StatusHistorySerializer,
    RoadmapMilestoneSerializer,
)


class FeatureRequestViewSet(viewsets.ModelViewSet):
    queryset = FeatureRequest.objects.all()
    serializer_class = FeatureRequestSerializer
    permission_classes = [IsAuthenticated]


class VoteViewSet(viewsets.ModelViewSet):
    queryset = Vote.objects.all()
    serializer_class = VoteSerializer
    permission_classes = [IsAuthenticated]


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]


class StatusHistoryViewSet(viewsets.ModelViewSet):
    queryset = StatusHistory.objects.all()
    serializer_class = StatusHistorySerializer
    permission_classes = [IsAuthenticated]


class RoadmapMilestoneViewSet(viewsets.ModelViewSet):
    queryset = RoadmapMilestone.objects.all()
    serializer_class = RoadmapMilestoneSerializer
    permission_classes = [IsAuthenticated]
