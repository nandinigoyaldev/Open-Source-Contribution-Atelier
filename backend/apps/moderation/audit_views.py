from datetime import datetime

from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.moderation.models import ContentReport, ModerationAuditEvent
from apps.moderation.serializers import ModerationAuditEventSerializer
from apps.moderation.views import IsModeratorOrAdmin

from .audit_utils import safe_parse_date


class ModerationAuditPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ModerationAuditTrailListView(generics.ListAPIView):
    serializer_class = ModerationAuditEventSerializer
    permission_classes = [IsModeratorOrAdmin]
    pagination_class = ModerationAuditPagination

    def get_queryset(self):
        qs = ModerationAuditEvent.objects.select_related("content_report", "moderator")

        status_param = self.request.query_params.get("status")
        if status_param and status_param != "ALL":
            qs = qs.filter(status_after=status_param)

        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(event_type__icontains=q)
                | Q(reason__icontains=q)
                | Q(content_report__category__icontains=q)
                | Q(content_report__object_id__icontains=q)
            )

        from_str = self.request.query_params.get("from")
        to_str = self.request.query_params.get("to")

        from_date = safe_parse_date(from_str)
        to_date = safe_parse_date(to_str)

        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        return qs.order_by("-created_at")

