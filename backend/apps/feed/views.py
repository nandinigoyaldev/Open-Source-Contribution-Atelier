from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import FeedEvent
from .serializers import FeedEventSerializer


class FeedEventViewSet(viewsets.ModelViewSet):
    queryset = FeedEvent.objects.all()
    serializer_class = FeedEventSerializer
    permission_classes = [IsAuthenticated]
