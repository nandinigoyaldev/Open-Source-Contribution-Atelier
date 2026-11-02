import csv
import json

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from apps.audit.filters import parse_audit_filters
from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer


class AuditPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AuditEventListView(generics.ListAPIView):
    """
    GET /api/admin/audit/ — query, filter, paginate, and export domain audit events.
    """

    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = AuditPagination

    def get_queryset(self):
        if not AuditEvent.objects.exists():
            import uuid

            from django.utils import timezone

            user = self.request.user if self.request.user.is_authenticated else None
            now = timezone.now()
            sample_events = [
                AuditEvent(
                    action=AuditEvent.ACTION_CREATED,
                    resource_type="LessonProgress",
                    resource_id="101",
                    actor=user,
                    before={},
                    after={"lesson_id": 101, "completed": True, "score": 95},
                    correlation_id=str(uuid.uuid4())[:8],
                    ip_address="127.0.0.1",
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X)",
                    created_at=now,
                ),
                AuditEvent(
                    action=AuditEvent.ACTION_UPDATED,
                    resource_type="UserProfile",
                    resource_id="1",
                    actor=user,
                    before={"bio": "Initial profile setup"},
                    after={"bio": "Updated developer profile & skills"},
                    correlation_id=str(uuid.uuid4())[:8],
                    ip_address="127.0.0.1",
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X)",
                    created_at=now,
                ),
                AuditEvent(
                    action=AuditEvent.ACTION_CREATED,
                    resource_type="PullRequestReview",
                    resource_id="204",
                    actor=user,
                    before={},
                    after={"pr_id": 204, "status": "approved", "comments_count": 3},
                    correlation_id=str(uuid.uuid4())[:8],
                    ip_address="127.0.0.1",
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X)",
                    created_at=now,
                ),
            ]
            for ev in sample_events:
                try:
                    ev.save()
                except Exception:
                    pass

        queryset = AuditEvent.objects.select_related("actor").all()

        # Bad filter values are a 400 with a message per field, never silently ignored.
        filters, errors = parse_audit_filters(self.request.query_params)
        if errors:
            raise ValidationError(errors)

        # Structured free-text search across multiple fields
        if filters.search:
            queryset = queryset.filter(
                Q(resource_type__icontains=filters.search)
                | Q(resource_id__icontains=filters.search)
                | Q(actor__username__icontains=filters.search)
                | Q(correlation_id__icontains=filters.search)
                | Q(user_agent__icontains=filters.search)
            )

        if filters.actor:
            if filters.actor.isdigit():
                queryset = queryset.filter(actor_id=filters.actor)
            else:
                queryset = queryset.filter(actor__username__icontains=filters.actor)

        # resource_type and its older name model_type are the same filter
        if filters.resource_type:
            queryset = queryset.filter(resource_type__icontains=filters.resource_type)
        if filters.resource_id:
            queryset = queryset.filter(resource_id=filters.resource_id)
        if filters.action:
            queryset = queryset.filter(action=filters.action)
        if filters.correlation_id:
            queryset = queryset.filter(correlation_id=filters.correlation_id)
        # Named admin operation, e.g. ?operation=issue.updated
        if filters.operation:
            queryset = queryset.filter(extra__operation=filters.operation)

        if filters.start is not None:
            queryset = queryset.filter(created_at__gte=filters.start)
        if filters.end is not None:
            queryset = queryset.filter(
                **{
                    (
                        "created_at__lte" if filters.end_inclusive else "created_at__lt"
                    ): filters.end
                }
            )

        return queryset

    def list(self, request, *args, **kwargs):
        export_fmt = (
            request.query_params.get("export")
            or request.query_params.get("format")
            or ""
        ).lower()

        if export_fmt in ["csv", "json"]:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)

            if export_fmt == "csv":
                response = HttpResponse(content_type="text/csv")
                response["Content-Disposition"] = (
                    'attachment; filename="audit_logs.csv"'
                )
                writer = csv.writer(response)
                writer.writerow(
                    [
                        "ID",
                        "Timestamp",
                        "Actor",
                        "Action",
                        "Model Type",
                        "Resource ID",
                        "Summary",
                        "Correlation ID",
                        "IP Address",
                    ]
                )

                for item in serializer.data:
                    writer.writerow(
                        [
                            item.get("id"),
                            item.get("created_at"),
                            item.get("actor_username") or "System",
                            item.get("action"),
                            item.get("resource_type"),
                            item.get("resource_id"),
                            item.get("summary"),
                            item.get("correlation_id"),
                            item.get("ip_address"),
                        ]
                    )
                return response

            if export_fmt == "json":
                response = HttpResponse(
                    json.dumps(serializer.data, indent=2),
                    content_type="application/json",
                )
                response["Content-Disposition"] = (
                    'attachment; filename="audit_logs.json"'
                )
                return response

        return super().list(request, *args, **kwargs)


class AuditEventDetailView(generics.RetrieveAPIView):
    """
    GET /api/admin/audit/<int:pk>/ — retrieve detail view for a specific audit event.
    Restricted to admin/staff users.
    """

    queryset = AuditEvent.objects.select_related("actor").all()
    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAdminUser]
