from rest_framework import serializers

from .models import SearchDocument


class SearchDocumentSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = SearchDocument
        fields = ["id", "title", "body_text", "type", "url"]

    def get_type(self, obj):
        return obj.content_type.model.title()

    def get_url(self, obj):
        # A simple helper to return API paths based on the content type
        model_name = obj.content_type.model
        if model_name == "lesson":
            return f"/api/content/lessons/{obj.object_id}/"
        elif model_name == "user":
            return f"/api/users/{obj.object_id}/"
        elif model_name == "challenge":
            return f"/api/challenges/{obj.object_id}/"
        elif model_name == "issue":
            return f"/api/dashboard/issues/{obj.object_id}/"
        return f"/api/{model_name}/{obj.object_id}/"
