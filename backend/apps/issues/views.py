from rest_framework import viewsets, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.issues.models import IssueReport
from apps.issues.serializers import IssueReportSerializer


class IssueReportViewSet(viewsets.ModelViewSet):
    queryset = IssueReport.objects.all()
    serializer_class = IssueReportSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    # Allow anyone to create a report (anonymous or authenticated)
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        # Restrict reading and updating to admins/staff
        if self.action in ["list", "retrieve", "update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save()
