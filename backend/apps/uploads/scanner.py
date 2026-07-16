"""ClamAV integration for quarantined uploads."""

from __future__ import annotations

from dataclasses import dataclass

import pyclamd
from django.conf import settings


class ScannerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ScanResult:
    infected: bool
    signature: str = ""


def get_clamav_client():
    socket_path = getattr(settings, "CLAMAV_SOCKET", "")
    host = getattr(settings, "CLAMAV_HOST", "127.0.0.1")
    port = int(getattr(settings, "CLAMAV_PORT", 3310))

    client = pyclamd.ClamdUnixSocket(socket_path) if socket_path else pyclamd.ClamdNetworkSocket(host, port)
    try:
        client.ping()
    except Exception as exc:
        raise ScannerUnavailable("ClamAV is unavailable.") from exc
    return client


def scan_file(file_path: str) -> ScanResult:
    client = get_clamav_client()
    result = client.scan_file(file_path)
    if not result:
        return ScanResult(infected=False)

    _, details = next(iter(result.items()))
    status, signature = details
    return ScanResult(infected=status == "FOUND", signature=signature or "")
