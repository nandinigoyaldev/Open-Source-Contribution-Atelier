# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
"""Admin-only API for bulk curriculum imports."""

from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import CurriculumImport
from .services import curriculum_import as ci
from .services import curriculum_import_jobs as jobs
from .tasks import enqueue, publish_curriculum_import, validate_curriculum_import


class CurriculumImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurriculumImport
        fields = [
            "id",
            "original_name",
            "sha256",
            "status",
            "cursor",
            "total_lessons",
            "report",
            "error",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CurriculumImportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ``POST``   upload an archive (multipart field ``archive``) and start validation.
    ``GET``    list imports, or fetch one to read its status and report (preview).
    ``POST {id}/publish/``  publish a previewed import in one transaction.
    """

    queryset = CurriculumImport.objects.all()
    serializer_class = CurriculumImportSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser]

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("archive")
        if upload is None:
            return Response(
                {"detail": "Attach the zip archive as the 'archive' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > jobs.max_archive_bytes():
            return Response(
                {"detail": f"Archive is larger than {jobs.max_archive_bytes()} bytes."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        imp = jobs.create_import(upload.read(), name=upload.name, user=request.user)
        enqueue(validate_curriculum_import, imp.pk)
        imp.refresh_from_db()
        return Response(self.get_serializer(imp).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        imp = self.get_object()
        if imp.status != CurriculumImport.PREVIEWED:
            return Response(
                {
                    "detail": f"Import is {imp.status}; only a previewed import "
                    "can be published."
                },
                status=status.HTTP_409_CONFLICT,
            )
        enqueue(publish_curriculum_import, imp.pk)
        imp.refresh_from_db()
        return Response(self.get_serializer(imp).data, status=status.HTTP_202_ACCEPTED)
