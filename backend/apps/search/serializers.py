from rest_framework import serializers

from .models import SearchAnalytics, SearchDocument


class SearchAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchAnalytics
        fields = ["query", "result_count", "user", "ip_address"]
        read_only_fields = ["user", "ip_address"]


class SearchDocumentSerializer(serializers.ModelSerializer):
    """
    Serializes search results.

    Extra read-only fields injected by the view when highlighting is active:
      - highlighted_title
      - highlighted_description
      - highlighted_body
    """

    type = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    # Highlight fields — set by the view via annotation; fall back to plain text
    highlighted_title = serializers.SerializerMethodField()
    highlighted_description = serializers.SerializerMethodField()
    highlighted_body = serializers.SerializerMethodField()

    class Meta:
        model = SearchDocument
        fields = [
            "id",
            "title",
            "description",
            "tags",
            "body_text",
            "type",
            "url",
            "highlighted_title",
            "highlighted_description",
            "highlighted_body",
        ]

    # --- type & url helpers ------------------------------------------------

    def get_type(self, obj):
        return obj.content_type.model.title()

    def get_url(self, obj):
        """Return the canonical API path for each content type."""
        model_name = obj.content_type.model
        url_map = {
            "lesson": f"/api/content/lessons/{obj.object_id}/",
            "user": f"/api/users/{obj.object_id}/",
            "challenge": f"/api/challenges/{obj.object_id}/",
            "issue": f"/api/dashboard/issues/{obj.object_id}/",
        }
        return url_map.get(model_name, f"/api/{model_name}/{obj.object_id}/")

    # --- highlight helpers -------------------------------------------------

    def _get_annotation(self, obj, annotation_name, fallback_field):
        """
        Return the annotated highlight value if present, otherwise plain text.
        The view annotates the queryset with SearchHeadline values.
        """
        value = getattr(obj, annotation_name, None)
        return value if value is not None else getattr(obj, fallback_field, "")

    def get_highlighted_title(self, obj):
        return self._get_annotation(obj, "headline_title", "title")

    def get_highlighted_description(self, obj):
        return self._get_annotation(obj, "headline_description", "description")

    def get_highlighted_body(self, obj):
        return self._get_annotation(obj, "headline_body", "body_text")
