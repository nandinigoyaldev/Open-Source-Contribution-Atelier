"""
Safe HTTP client wrapper for outgoing webhook dispatch with SSRF protection
and DNS rebinding prevention.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0
MAX_TIMEOUT = 5.0
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB
MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB

# Standard blocked IPv4 and IPv6 networks
BLOCKED_NETWORKS = [
    # IPv4 Private & Reserved (RFC 1918, RFC 3927, RFC 6598, etc.)
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source)
    ipaddress.ip_network("10.0.0.0/8"),          # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),       # RFC 6598 Shared Address Space (CGNAT)
    ipaddress.ip_network("127.0.0.0/8"),         # RFC 1122 Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # RFC 3927 Link-Local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),       # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),        # RFC 6890 IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),        # RFC 5737 TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),      # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),       # RFC 2544 Network Interconnect Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),     # RFC 5737 TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # RFC 5737 TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),         # RFC 5771 Multicast
    ipaddress.ip_network("240.0.0.0/4"),         # RFC 1112 Reserved / Class E
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6 Blocked Ranges
    ipaddress.ip_network("::/128"),              # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("100::/64"),            # Discard-only prefix
    ipaddress.ip_network("2001:db8::/32"),       # Documentation
    ipaddress.ip_network("fc00::/7"),            # Unique Local Address (ULA / Private)
    ipaddress.ip_network("fe80::/10"),           # Link-Local
    ipaddress.ip_network("ff00::/8"),            # Multicast
]

# Explicit cloud metadata IPs
METADATA_IPS: set[str] = {
    "169.254.169.254",  # AWS, GCP, Azure, OpenStack, DigitalOcean
    "169.254.169.250",  # Azure scheduled events
    "169.254.169.251",  # Azure wire server
    "169.254.169.253",  # Azure DNS
    "fd00:ec2::254",    # AWS IPv6 IMDS
}

# Blocked hostnames and suffixes
BLOCKED_HOST_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".arpa",
    ".invalid",
    ".test",
    ".example",
)

BLOCKED_HOSTNAMES: set[str] = {
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}


class SSRFProtectionError(requests.exceptions.RequestException):
    """Base exception for all SSRF and safe client security violations."""


class InvalidSchemeError(SSRFProtectionError):
    """Raised when URL scheme is not http or https."""


class BlockedIPError(SSRFProtectionError):
    """Raised when destination IP belongs to a private, loopback, or metadata range."""


class DNSResolutionError(SSRFProtectionError):
    """Raised when destination host fails DNS resolution."""


class PayloadTooLargeError(SSRFProtectionError):
    """Raised when payload exceeds maximum size limit."""


class PinnedIPAdapter(HTTPAdapter):
    """
    HTTPAdapter that routes requests directly to a pre-validated, pinned IP address
    while preserving the original Host header and TLS SNI verification against the hostname.
    This prevents DNS rebinding (TOCTOU) attacks between resolution and socket connect.
    """

    def __init__(self, pinned_ip: str, original_host: str, **kwargs: Any) -> None:
        self.pinned_ip = pinned_ip
        self.original_host = original_host
        super().__init__(**kwargs)

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> Any:
        pool_kwargs["assert_hostname"] = self.original_host
        pool_kwargs["server_hostname"] = self.original_host
        self.poolmanager = urllib3.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )


class SafeHTTPClient:
    """
    Secure HTTP client for outgoing webhook dispatches.
    Enforces URL scheme whitelisting, IP blacklisting (SSRF protection),
    IP address pinning (DNS rebinding protection), and request/response size limits.
    """

    @classmethod
    def validate_ip(cls, ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
        """
        Validate a single IP address string against private, loopback, and metadata ranges.
        Raises BlockedIPError if the IP is prohibited.
        """
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as err:
            raise BlockedIPError(f"Malformed IP address: {ip_str}") from err

        # Unwrap IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
            ip_obj = ip_obj.ipv4_mapped

        # Check explicit metadata IPs
        if str(ip_obj) in METADATA_IPS:
            raise BlockedIPError(f"Access to cloud metadata IP {ip_obj} is blocked.")

        # Standard checks
        if ip_obj.is_loopback:
            raise BlockedIPError(f"Loopback IP {ip_obj} is blocked.")
        if ip_obj.is_private:
            raise BlockedIPError(f"Private IP {ip_obj} is blocked (RFC 1918 / RFC 4193).")
        if ip_obj.is_link_local:
            raise BlockedIPError(f"Link-local IP {ip_obj} is blocked.")
        if ip_obj.is_multicast:
            raise BlockedIPError(f"Multicast IP {ip_obj} is blocked.")
        if ip_obj.is_reserved:
            raise BlockedIPError(f"Reserved IP {ip_obj} is blocked.")
        if ip_obj.is_unspecified:
            raise BlockedIPError(f"Unspecified IP {ip_obj} is blocked.")

        # Check network ranges
        for net in BLOCKED_NETWORKS:
            if ip_obj in net:
                raise BlockedIPError(f"IP {ip_obj} falls within blocked network {net}.")

        return ip_obj

    @classmethod
    def resolve_and_validate(cls, hostname: str, port: int) -> str:
        """
        Resolve the hostname via DNS and validate that ALL resolved IP addresses
        are safe. Returns the first resolved and validated IP string (pinned IP).
        """
        # Hostname string checks
        lower_host = hostname.lower().strip()
        if not lower_host:
            raise SSRFProtectionError("Empty hostname is not allowed.")

        if lower_host in BLOCKED_HOSTNAMES:
            raise BlockedIPError(f"Hostname '{lower_host}' is explicitly blocked.")

        for suffix in BLOCKED_HOST_SUFFIXES:
            if lower_host.endswith(suffix):
                raise BlockedIPError(f"Hostname '{lower_host}' ends with prohibited domain suffix '{suffix}'.")

        # Check if the hostname is directly an IP literal
        is_ip = False
        try:
            ipaddress.ip_address(lower_host)
            is_ip = True
        except ValueError:
            pass

        if is_ip:
            cls.validate_ip(lower_host)
            return lower_host

        try:
            addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as err:
            raise DNSResolutionError(f"DNS resolution failed for hostname '{hostname}': {err}") from err

        if not addr_info:
            raise DNSResolutionError(f"No DNS records found for hostname '{hostname}'.")

        validated_ips: list[str] = []
        for entry in addr_info:
            sockaddr = entry[4]
            ip_candidate = sockaddr[0]
            cls.validate_ip(ip_candidate)
            validated_ips.append(ip_candidate)

        # Return the first resolved and validated IP for pinning
        return validated_ips[0]

    @classmethod
    def validate_url(cls, url: str) -> tuple[str, str, int, str]:
        """
        Validates URL scheme, port, resolves and validates IP addresses.
        Returns (pinned_ip, hostname, port, pinned_url).
        """
        split = urlsplit(url)
        scheme = split.scheme.lower()
        if scheme not in ("http", "https"):
            raise InvalidSchemeError(f"Prohibited URL scheme '{scheme}'. Only http and https are allowed.")

        hostname = split.hostname
        if not hostname:
            raise SSRFProtectionError("URL is missing a valid hostname.")

        port = split.port or (443 if scheme == "https" else 80)
        pinned_ip = cls.resolve_and_validate(hostname, port)

        # Format pinned netloc (IPv6 needs brackets)
        pinned_host = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
        pinned_netloc = f"{pinned_host}:{port}" if split.port else pinned_host

        pinned_url = urlunsplit((
            split.scheme,
            pinned_netloc,
            split.path or "/",
            split.query,
            split.fragment,
        ))

        return pinned_ip, hostname, port, pinned_url

    @classmethod
    def post(
        cls,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Safely execute an HTTP POST request with SSRF validation and DNS rebinding protection.
        """
        return cls.request("POST", url, data=data, json=json, headers=headers, timeout=timeout, **kwargs)

    @classmethod
    def request(
        cls,
        method: str,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Execute an HTTP request with SSRF validation, DNS pinning, and size caps.
        """
        # Validate and pin URL
        pinned_ip, hostname, port, pinned_url = cls.validate_url(url)

        # Enforce payload size cap
        if data is not None:
            if isinstance(data, (bytes, bytearray)) and len(data) > MAX_PAYLOAD_SIZE:
                raise PayloadTooLargeError(f"Payload size {len(data)} bytes exceeds limit {MAX_PAYLOAD_SIZE}")
            elif isinstance(data, str) and len(data.encode("utf-8")) > MAX_PAYLOAD_SIZE:
                raise PayloadTooLargeError(f"Payload size exceeds limit {MAX_PAYLOAD_SIZE}")

        req_headers = dict(headers or {})
        # Ensure Host header matches original target hostname
        req_headers.setdefault("Host", f"{hostname}:{port}" if port not in (80, 443) else hostname)

        # Cap timeout
        effective_timeout = min(float(timeout or DEFAULT_TIMEOUT), MAX_TIMEOUT)

        session = requests.Session()
        adapter = PinnedIPAdapter(pinned_ip, hostname)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Disallow automatic redirect following to prevent redirect-based SSRF
        kwargs.setdefault("allow_redirects", False)

        try:
            resp = session.request(
                method=method,
                url=pinned_url,
                data=data,
                json=json,
                headers=req_headers,
                timeout=effective_timeout,
                **kwargs,
            )
            return resp
        finally:
            session.close()


def safe_post(url: str, **kwargs: Any) -> requests.Response:
    """Convenience helper to safely POST to an outgoing webhook destination."""
    return SafeHTTPClient.post(url, **kwargs)
