from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Note
from .serializers import NoteSerializer


class NotePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class NoteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NoteSerializer
    pagination_class = NotePagination

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        client_id = request.data.get("client_id")
        if client_id:
            existing = Note.objects.filter(
                user=request.user, client_id=client_id
            ).first()
            if existing:
                serializer = self.get_serializer(existing)
                return Response(serializer.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        expected_version = request.data.get("expected_version") or request.data.get(
            "version"
        )
        if expected_version is not None and int(expected_version) != instance.version:
            return Response(
                {
                    "error": "conflict",
                    "message": "Note has been modified by another device or session.",
                    "conflict_type": "version_mismatch",
                    "server_version": instance.version,
                    "server_data": self.get_serializer(instance).data,
                    "server_updated_at": instance.updated_at.isoformat(),
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance.version += 1
        self.perform_update(serializer)
        return Response(serializer.data)
