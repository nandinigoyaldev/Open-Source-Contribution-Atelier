"""
Unit tests for SSRF protection and DNS rebinding prevention in webhook dispatchers.
"""

import socket
from unittest.mock import MagicMock, patch

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret-key-ssrf-testing",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "apps.webhooks",
        ],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    )
    django.setup()

import pytest
import requests
from apps.webhooks.services.safe_client import (
    BlockedIPError,
    DNSResolutionError,
    InvalidSchemeError,
    PayloadTooLargeError,
    SafeHTTPClient,
)


class TestSSRFIPValidation:
    """Tests asserting that all private, loopback, link-local, and metadata IPs are rejected."""

    @pytest.mark.parametrize(
        "blocked_ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "127.1.2.3",
            "10.0.0.1",
            "10.254.254.254",
            "172.16.0.1",
            "172.24.5.10",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.1.254",
            "169.254.169.254",  # AWS / Cloud Metadata
            "169.254.169.250",  # Azure Metadata
            "169.254.1.1",      # Link-local
            "0.0.0.0",
            "100.64.0.1",       # CGNAT
            "192.0.2.1",        # TEST-NET-1
            "198.51.100.1",     # TEST-NET-2
            "203.0.113.1",      # TEST-NET-3
            "224.0.0.1",        # Multicast
            "240.0.0.1",        # Reserved
            "255.255.255.255",
            "::1",              # IPv6 loopback
            "fe80::1",          # IPv6 link-local
            "fc00::1",          # IPv6 ULA
            "fd00:ec2::254",    # AWS IPv6 IMDS
            "::ffff:127.0.0.1", # IPv4-mapped IPv6 loopback
            "::ffff:169.254.169.254",  # IPv4-mapped IPv6 metadata
            "::ffff:10.0.0.1",  # IPv4-mapped IPv6 private
        ],
    )
    def test_rejection_of_blocked_ips(self, blocked_ip):
        with pytest.raises(BlockedIPError):
            SafeHTTPClient.validate_ip(blocked_ip)

    def test_allowed_public_ips(self):
        public_ips = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111"]
        for ip in public_ips:
            res = SafeHTTPClient.validate_ip(ip)
            assert str(res) == ip or str(res).lower() == ip.lower()


class TestSSRFHostnameAndSchemeValidation:
    """Tests asserting rejection of prohibited schemes and internal domains."""

    @pytest.mark.parametrize(
        "bad_scheme_url",
        [
            "file:///etc/passwd",
            "ftp://ftp.example.com/file",
            "gopher://127.0.0.1:6379/_INFO",
            "dict://127.0.0.1:11211/stat",
            "data:text/plain;base64,SGVsbG8=",
        ],
    )
    def test_prohibited_schemes(self, bad_scheme_url):
        with pytest.raises(InvalidSchemeError):
            SafeHTTPClient.validate_url(bad_scheme_url)

    @pytest.mark.parametrize(
        "bad_domain_url",
        [
            "http://localhost/webhook",
            "http://localhost:8080/hook",
            "http://test.localhost/api",
            "http://backend.internal/events",
            "http://app.local/webhook",
            "http://cluster.lan/endpoint",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://instance-data/latest/meta-data/",
        ],
    )
    def test_prohibited_hostnames(self, bad_domain_url):
        with pytest.raises(BlockedIPError):
            SafeHTTPClient.validate_url(bad_domain_url)

    def test_dns_resolution_failure(self):
        with (
            patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")),
            pytest.raises(DNSResolutionError),
        ):
            SafeHTTPClient.validate_url("https://this-domain-does-not-exist-at-all-12345.com/webhook")

    def test_dns_resolving_to_private_ip_is_blocked(self):
        mock_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.50", 443))]
        with (
            patch("socket.getaddrinfo", return_value=mock_addr),
            pytest.raises(BlockedIPError),
        ):
            SafeHTTPClient.validate_url("https://malicious-dns.com/webhook")

    def test_dns_resolving_to_metadata_ip_is_blocked(self):
        mock_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
        with (
            patch("socket.getaddrinfo", return_value=mock_addr),
            pytest.raises(BlockedIPError),
        ):
            SafeHTTPClient.validate_url("http://cloud-rebind.com/webhook")

    def test_dns_mixed_records_with_one_private_record_is_blocked(self):
        mock_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]
        with (
            patch("socket.getaddrinfo", return_value=mock_addr),
            pytest.raises(BlockedIPError),
        ):
            SafeHTTPClient.validate_url("https://mixed-dns.com/webhook")


class TestDNSRebindingAndPinning:
    """Tests asserting IP pinning prevents DNS rebinding (TOCTOU) attacks."""

    @patch("requests.Session.request")
    def test_pinned_ip_used_in_request_url_and_host_header_preserved(self, mock_session_request):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_session_request.return_value = mock_resp

        mock_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with patch("socket.getaddrinfo", return_value=mock_addr):
            resp = SafeHTTPClient.post("https://example.com/webhook", data=b'{"test": 1}')
            assert resp.status_code == 200

            _, call_kwargs = mock_session_request.call_args
            assert call_kwargs["method"] == "POST"
            # The URL sent on wire connects directly to pinned IP
            assert "93.184.216.34" in call_kwargs["url"]
            # The Host header remains the original domain name
            assert call_kwargs["headers"]["Host"] == "example.com"
            assert call_kwargs["allow_redirects"] is False

    def test_payload_size_limit_enforced(self):
        huge_payload = b"A" * (1024 * 1024 + 50)
        with pytest.raises(PayloadTooLargeError):
            SafeHTTPClient.post("https://example.com/webhook", data=huge_payload)


class TestTaskAndDLQIntegration:
    """Tests asserting SSRF protection in Celery tasks and Dead Letter Queue handling."""

    @patch("apps.webhooks.tasks._move_to_dlq")
    @patch("apps.webhooks.tasks.WebhookDeliveryLog.objects.create")
    @patch("apps.webhooks.tasks.WebhookDelivery.objects")
    def test_deliver_webhook_moves_ssrf_attempt_to_dlq(
        self, mock_delivery_mgr, mock_log_create, mock_dlq
    ):
        from apps.webhooks.tasks import deliver_webhook

        mock_delivery = MagicMock()
        mock_delivery.id = 101
        mock_delivery.endpoint.secret = "test-secret-signing-key"
        mock_delivery.endpoint.target_url = "http://169.254.169.254/latest/meta-data/"
        mock_delivery.endpoint.is_circuit_open.return_value = False
        mock_delivery.endpoint.is_half_open.return_value = False
        mock_delivery.payload = {"ping": "pong"}
        mock_delivery.event_type = "test.event"

        mock_delivery_mgr.get.return_value = mock_delivery
        mock_delivery_mgr.filter.return_value.exclude.return_value.update.return_value = 1

        deliver_webhook(101)

        assert mock_delivery.status == "dead"
        assert "SSRF Blocked" in mock_delivery.response_body
        mock_delivery.save.assert_called()
        mock_dlq.assert_called_once_with(mock_delivery, reason=mock_delivery.response_body)

    @patch("apps.webhooks.tasks._move_to_dlq")
    @patch("apps.webhooks.tasks.WebhookDeliveryLog.objects.create")
    @patch("apps.webhooks.tasks.WebhookDelivery.objects")
    def test_deliver_webhook_blocks_internal_localhost(
        self, mock_delivery_mgr, mock_log_create, mock_dlq
    ):
        from apps.webhooks.tasks import deliver_webhook

        mock_delivery = MagicMock()
        mock_delivery.id = 102
        mock_delivery.endpoint.secret = "test-secret-signing-key"
        mock_delivery.endpoint.target_url = "http://127.0.0.1:8000/internal-admin/"
        mock_delivery.endpoint.is_circuit_open.return_value = False
        mock_delivery.endpoint.is_half_open.return_value = False
        mock_delivery.payload = {"ping": "pong"}
        mock_delivery.event_type = "test.event"

        mock_delivery_mgr.get.return_value = mock_delivery
        mock_delivery_mgr.filter.return_value.exclude.return_value.update.return_value = 1

        deliver_webhook(102)

        assert mock_delivery.status == "dead"
        assert "SSRF Blocked" in mock_delivery.response_body
        mock_dlq.assert_called_once()
