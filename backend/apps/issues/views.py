from rest_framework import permissions, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

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


from django.db import transaction
from django_q.tasks import async_task
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.issues.models import Bounty, BountySubmission
from apps.issues.serializers import BountySerializer, BountySubmissionSerializer
from apps.progress.models import XPEvent, XPMultiplierEvent


class BountyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bounty.objects.select_related("badge").all()
    serializer_class = BountySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def claim(self, request, pk=None):
        bounty = self.get_object()
        if bounty.status != Bounty.Status.OPEN:
            return Response(
                {"error": "Bounty is not open for claiming."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bounty.status = Bounty.Status.CLAIMED
        bounty.claimed_by = request.user
        bounty.save()

        return Response({"status": "Bounty claimed successfully!"})

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def submit(self, request, pk=None):
        bounty = self.get_object()

        if bounty.status != Bounty.Status.CLAIMED or bounty.claimed_by != request.user:
            return Response(
                {"error": "You must claim this bounty before submitting."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code_patch = request.data.get("code_patch", "")
        if not code_patch:
            return Response(
                {"error": "No code submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            submission = BountySubmission.objects.create(
                bounty=bounty,
                user=request.user,
                code_patch=code_patch,
                status=BountySubmission.Status.PASSED,
            )

            bounty.status = Bounty.Status.COMPLETED
            bounty.save()

            # Award XP
            multiplier = XPMultiplierEvent.get_active_multiplier()
            xp_earned = int(bounty.xp_reward * multiplier)
            XPEvent.objects.create(
                user=request.user,
                source_type="bounty",
                source_id=bounty.id,
                base_points=bounty.xp_reward,
                multiplier=multiplier,
                xp_delta=xp_earned,
            )

            # Award badge asynchronously if the bounty has one configured
            if bounty.badge_id:
                async_task(
                    "apps.progress.tasks.award_specific_badge",
                    request.user.id,
                    bounty.badge_id,
                )

        return Response(
            {
                "status": "Bounty completed successfully!",
                "xp_earned": xp_earned,
            }
        )
