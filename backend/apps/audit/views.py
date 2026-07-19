from rest_framework import generics, permissions
from django.utils.dateparse import parse_datetime
from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer


class AuditEventListView(generics.ListAPIView):
    """
    GET /api/audit/ — query and filter domain audit events.
    Restricted to admin users (superusers/staff).
    """

    serializer_class = AuditEventSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = AuditEvent.objects.select_related("actor").all()

        actor = self.request.query_params.get("actor")
        if actor:
            if actor.isdigit():
                queryset = queryset.filter(actor_id=actor)
            else:
                queryset = queryset.filter(actor__username__iexact=actor)

        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            queryset = queryset.filter(resource_type__iexact=resource_type)

        resource_id = self.request.query_params.get("resource_id")
        if resource_id:
            queryset = queryset.filter(resource_id=resource_id)

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        correlation_id = self.request.query_params.get("correlation_id")
        if correlation_id:
            queryset = queryset.filter(correlation_id=correlation_id)

        start_date = self.request.query_params.get("start_date")
        if start_date:
            dt = parse_datetime(start_date)
            if dt:
                queryset = queryset.filter(created_at__gte=dt)

        end_date = self.request.query_params.get("end_date")
        if end_date:
            dt = parse_datetime(end_date)
            if dt:
                queryset = queryset.filter(created_at__lte=dt)

        return queryset
