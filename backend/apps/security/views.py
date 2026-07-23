from datetime import timedelta
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AutoFixPR,
    VulnerabilityItem,
    VulnerabilityReport,
    VulnerabilitySuppression,
)
from .serializers import (
    AutoFixPRSerializer,
    VulnerabilityItemSerializer,
    VulnerabilityReportSerializer,
    VulnerabilitySuppressionSerializer,
)


class VulnerabilityReportViewSet(viewsets.ModelViewSet):
    queryset = VulnerabilityReport.objects.all()
    serializer_class = VulnerabilityReportSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"])
    def ingest(self, request):
        """
        Ingest scan results payload (JSON summary or SARIF representation).
        """
        data = request.data
        commit_sha = data.get("commit_sha", "")
        branch = data.get("branch", "main")
        ecosystem = data.get("ecosystem", "ALL")
        matches = data.get("matches", [])

        crit, high, med, low = 0, 0, 0, 0
        report = VulnerabilityReport.objects.create(
            commit_sha=commit_sha,
            branch=branch,
            ecosystem=ecosystem,
            summary_json=data.get("summary", {}),
        )

        for match in matches:
            sev = str(match.get("severity", "LOW")).upper()
            if sev == "CRITICAL":
                crit += 1
            elif sev == "HIGH":
                high += 1
            elif sev == "MEDIUM":
                med += 1
            else:
                low += 1

            VulnerabilityItem.objects.create(
                report=report,
                cve_id=match.get("cve_id", "CVE-UNKNOWN"),
                package_name=match.get("package_name", "unknown"),
                installed_version=match.get("installed_version", "0.0.0"),
                fixed_version=match.get("fixed_version", ""),
                severity=sev if sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] else "LOW",
                ecosystem=match.get("ecosystem", "python"),
                title=match.get("title", ""),
                description=match.get("description", ""),
                status="OPEN",
            )

        report.total_vulnerabilities = len(matches)
        report.critical_count = crit
        report.high_count = high
        report.medium_count = med
        report.low_count = low
        report.save()

        return Response(
            VulnerabilityReportSerializer(report).data, status=status.HTTP_201_CREATED
        )


class VulnerabilityItemViewSet(viewsets.ModelViewSet):
    queryset = VulnerabilityItem.objects.all()
    serializer_class = VulnerabilityItemSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        severity = self.request.query_params.get("severity")
        ecosystem = self.request.query_params.get("ecosystem")
        status_param = self.request.query_params.get("status")
        search = self.request.query_params.get("search")

        if severity:
            qs = qs.filter(severity=severity.upper())
        if ecosystem:
            qs = qs.filter(ecosystem=ecosystem.lower())
        if status_param:
            qs = qs.filter(status=status_param.upper())
        if search:
            qs = qs.filter(
                Q(cve_id__icontains=search)
                | Q(package_name__icontains=search)
                | Q(title__icontains=search)
            )

        return qs


class VulnerabilitySuppressionViewSet(viewsets.ModelViewSet):
    queryset = VulnerabilitySuppression.objects.all()
    serializer_class = VulnerabilitySuppressionSerializer
    permission_classes = [permissions.AllowAny]


class AutoFixPRViewSet(viewsets.ModelViewSet):
    queryset = AutoFixPR.objects.all()
    serializer_class = AutoFixPRSerializer
    permission_classes = [permissions.AllowAny]


class VulnerabilitySummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        latest_report = VulnerabilityReport.objects.first()

        total = VulnerabilityItem.objects.count()
        critical = VulnerabilityItem.objects.filter(severity="CRITICAL").count()
        high = VulnerabilityItem.objects.filter(severity="HIGH").count()
        medium = VulnerabilityItem.objects.filter(severity="MEDIUM").count()
        low = VulnerabilityItem.objects.filter(severity="LOW").count()

        open_count = VulnerabilityItem.objects.filter(status="OPEN").count()
        suppressed_count = VulnerabilityItem.objects.filter(status="SUPPRESSED").count()
        resolved_count = VulnerabilityItem.objects.filter(status="RESOLVED").count()
        active_autofix_prs = AutoFixPR.objects.filter(status="OPEN").count()

        # 14-day history trend
        trend = []
        now = timezone.now()
        for i in range(13, -1, -1):
            date_val = (now - timedelta(days=i)).date()
            reports_on_date = VulnerabilityReport.objects.filter(
                scan_date__date=date_val
            )
            c_cnt = reports_on_date.aggregate(s=Sum("critical_count"))["s"] or 0
            h_cnt = reports_on_date.aggregate(s=Sum("high_count"))["s"] or 0
            m_cnt = reports_on_date.aggregate(s=Sum("medium_count"))["s"] or 0
            l_cnt = reports_on_date.aggregate(s=Sum("low_count"))["s"] or 0

            trend.append(
                {
                    "date": date_val.strftime("%b %d"),
                    "critical": c_cnt,
                    "high": h_cnt,
                    "medium": m_cnt,
                    "low": l_cnt,
                    "total": c_cnt + h_cnt + m_cnt + l_cnt,
                }
            )

        suppressions = VulnerabilitySuppression.objects.all()
        suppression_data = VulnerabilitySuppressionSerializer(
            suppressions, many=True
        ).data

        return Response(
            {
                "latest_scan": (
                    VulnerabilityReportSerializer(latest_report).data
                    if latest_report
                    else None
                ),
                "metrics": {
                    "total": total,
                    "critical": critical,
                    "high": high,
                    "medium": medium,
                    "low": low,
                    "open": open_count,
                    "suppressed": suppressed_count,
                    "resolved": resolved_count,
                    "active_autofix_prs": active_autofix_prs,
                },
                "trend": trend,
                "suppressions": suppression_data,
            }
        )
