from rest_framework import serializers
from .models import PortfolioTemplate, GeneratedPortfolio


class PortfolioTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioTemplate
        fields = ["id", "name", "slug", "description", "is_active"]


class GeneratedPortfolioSerializer(serializers.ModelSerializer):
    template = PortfolioTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=PortfolioTemplate.objects.filter(is_active=True),
        source="template",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = GeneratedPortfolio
        fields = [
            "id",
            "template",
            "template_id",
            "format",
            "status",
            "sections_included",
            "file",
            "error_message",
            "created_at",
            "expires_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "file",
            "error_message",
            "created_at",
            "expires_at",
        ]


class GeneratePortfolioRequestSerializer(serializers.Serializer):
    format = serializers.ChoiceField(
        choices=GeneratedPortfolio.Format.choices, default=GeneratedPortfolio.Format.PDF
    )
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=PortfolioTemplate.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    sections_included = serializers.JSONField(default=dict)
