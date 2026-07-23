from rest_framework import serializers
from .models import FeedEvent


class FeedEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedEvent
        fields = "__all__"
