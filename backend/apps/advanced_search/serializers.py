from rest_framework import serializers
from .models import SearchEmbedding, UserSearchProfile, SearchAnalytics


class SearchEmbeddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchEmbedding
        fields = "__all__"


class UserSearchProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSearchProfile
        fields = "__all__"


class SearchAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchAnalytics
        fields = "__all__"
