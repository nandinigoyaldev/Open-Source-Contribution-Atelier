from datetime import timedelta
from django.utils import timezone
import pytest
from rest_framework.test import APIClient
from apps.security.models import (
    AutoFixPR,
    VulnerabilityItem,
    VulnerabilityReport,
    VulnerabilitySuppression,
)


@pytest.mark.django_db
class TestSecurityAPI:
    def setup_method(self):
        self.client = APIClient()

    def test_ingest_vulnerability_report(self):
        payload = {
            "commit_sha": "abc1234",
            "branch": "main",
            "ecosystem": "ALL",
            "matches": [
                {
                    "cve_id": "CVE-2023-1001",
                    "package_name": "requests",
                    "installed_version": "2.28.0",
                    "fixed_version": "2.31.0",
                    "severity": "CRITICAL",
                    "ecosystem": "python",
                    "title": "Remote code execution in requests",
                    "description": "High severity CVE test.",
                },
                {
                    "cve_id": "CVE-2023-1002",
                    "package_name": "express",
                    "installed_version": "4.17.1",
                    "fixed_version": "4.18.2",
                    "severity": "HIGH",
                    "ecosystem": "npm",
                    "title": "DoS in express",
                },
            ],
        }

        response = self.client.post(
            "/api/security/vulnerability-reports/ingest/", payload, format="json"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["commit_sha"] == "abc1234"
        assert data["total_vulnerabilities"] == 2
        assert data["critical_count"] == 1
        assert data["high_count"] == 1

    def test_vulnerability_item_filtering(self):
        report = VulnerabilityReport.objects.create(commit_sha="test_sha")
        VulnerabilityItem.objects.create(
            report=report,
            cve_id="CVE-2024-1111",
            package_name="django",
            installed_version="5.0.0",
            severity="CRITICAL",
            ecosystem="python",
        )
        VulnerabilityItem.objects.create(
            report=report,
            cve_id="CVE-2024-2222",
            package_name="lodash",
            installed_version="4.17.0",
            severity="LOW",
            ecosystem="npm",
        )

        resp_crit = self.client.get("/api/security/vulnerabilities/?severity=CRITICAL")
        assert resp_crit.status_code == 200
        res_crit = resp_crit.json()
        items_crit = (
            res_crit if isinstance(res_crit, list) else res_crit.get("results", [])
        )
        assert len(items_crit) == 1
        assert items_crit[0]["cve_id"] == "CVE-2024-1111"

        resp_npm = self.client.get("/api/security/vulnerabilities/?ecosystem=npm")
        assert resp_npm.status_code == 200
        res_npm = resp_npm.json()
        items_npm = res_npm if isinstance(res_npm, list) else res_npm.get("results", [])
        assert len(items_npm) == 1
        assert items_npm[0]["package_name"] == "lodash"

    def test_vulnerability_suppression_active(self):
        future_date = timezone.now().date() + timedelta(days=30)
        past_date = timezone.now().date() - timedelta(days=5)

        sup_active = VulnerabilitySuppression.objects.create(
            cve_id="CVE-2023-9999",
            package_name="foo",
            reason="Approved exception",
            expires_at=future_date,
        )
        sup_expired = VulnerabilitySuppression.objects.create(
            cve_id="CVE-2023-8888",
            package_name="bar",
            reason="Expired exception",
            expires_at=past_date,
        )

        assert sup_active.is_active is True
        assert sup_expired.is_active is False

    def test_vulnerability_summary_endpoint(self):
        report = VulnerabilityReport.objects.create(
            commit_sha="sha1", critical_count=1, high_count=2
        )
        VulnerabilityItem.objects.create(
            report=report,
            cve_id="CVE-2024-0001",
            package_name="pkg",
            installed_version="1.0.0",
            severity="CRITICAL",
            status="OPEN",
        )
        AutoFixPR.objects.create(
            pr_number=42,
            pr_url="https://github.com/org/repo/pull/42",
            status="OPEN",
        )

        resp = self.client.get("/api/security/summary/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"]["critical"] == 1
        assert data["metrics"]["open"] == 1
        assert data["metrics"]["active_autofix_prs"] == 1
        assert len(data["trend"]) == 14
