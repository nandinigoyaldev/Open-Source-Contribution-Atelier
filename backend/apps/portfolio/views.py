from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import PortfolioTemplate, GeneratedPortfolio
from .serializers import (
    PortfolioTemplateSerializer,
    GeneratedPortfolioSerializer,
    GeneratePortfolioRequestSerializer,
)
from .tasks import generate_portfolio_task


class PortfolioTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PortfolioTemplate.objects.filter(is_active=True)
    serializer_class = PortfolioTemplateSerializer
    permission_classes = [IsAuthenticated]


class GeneratedPortfolioViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = GeneratedPortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GeneratedPortfolio.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        serializer = GeneratePortfolioRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        portfolio = GeneratedPortfolio.objects.create(
            user=request.user,
            format=data["format"],
            template=data.get("template_id"),
            sections_included=data.get("sections_included", {}),
        )

        # Dispatch celery task
        generate_portfolio_task.delay(str(portfolio.id))

        response_serializer = self.get_serializer(portfolio)
        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        portfolio = self.get_object()

        if (
            portfolio.status != GeneratedPortfolio.Status.COMPLETED
            or not portfolio.file
        ):
            return Response(
                {"detail": "Portfolio is not ready for download or failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Return URL to the file, frontend can redirect or fetch
        return Response({"download_url": portfolio.file.url})
