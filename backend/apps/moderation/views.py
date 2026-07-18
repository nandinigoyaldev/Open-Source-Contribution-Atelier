from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError
from rest_framework import serializers
from apps.moderation.models import ContentReport, ModerationAuditEvent

from apps.moderation.serializers import (
    ContentReportSerializer,
    ModerationActionSerializer,
)




class IsModeratorOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_superuser)


class ContentReportListCreateView(generics.ListCreateAPIView):
    serializer_class = ContentReportSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [IsModeratorOrAdmin()]

    def get_queryset(self):
        # Admins see all pending reports by default
        qs = ContentReport.objects.all()
        status_param = self.request.query_params.get("status", "PENDING")
        if status_param and status_param != "ALL":
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        try:
            serializer.save(reporter=self.request.user)
        except IntegrityError:
            # Handle unique constraint violation
            raise serializers.ValidationError(
                {"error": "You have already reported this content."}
            )


class ContentReportActionView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def post(self, request, pk):

        report = generics.get_object_or_404(ContentReport, pk=pk)
        serializer = ModerationActionSerializer(data=request.data)

        if serializer.is_valid():
            new_status = serializer.validated_data["status"]
            report.status = new_status
            report.moderator = request.user

            if new_status == ContentReport.Status.APPROVED:
                # Need to hide the actual content
                content_obj = report.content_object
                if content_obj and hasattr(content_obj, "is_hidden"):
                    content_obj.is_hidden = True
                    content_obj.save(update_fields=["is_hidden"])
                report.action_taken = ContentReport.ActionTaken.HIDDEN
            elif new_status == ContentReport.Status.DISMISSED:
                report.action_taken = ContentReport.ActionTaken.NONE

            report.save()
            return Response(ContentReportSerializer(report).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
