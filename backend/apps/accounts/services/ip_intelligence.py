"""
Where an IP address is and what kind of network it belongs to.

The project ships no geolocation or ASN data and calls no outside service. The
default provider answers nothing. To turn on the travel and network checks, point
``LOGIN_RISK_IP_PROVIDER`` at a class with the same ``lookup`` method.
"""

from dataclasses import dataclass
from typing import Optional, Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class IPInfo:
    """What a provider knows about an address. Every part of it is optional."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country: str = ""
    asn: Optional[int] = None
    # A datacenter, proxy, VPN or Tor exit address.
    is_proxy: bool = False


class IPIntelligenceProvider(Protocol):
    def lookup(self, ip_address: str) -> Optional[IPInfo]:
        """Return what is known about the address, or None."""
        ...


class OfflineIPIntelligence:
    """Default provider: knows nothing and makes no network calls."""

    def lookup(self, ip_address: str) -> Optional[IPInfo]:
        return None


def get_ip_provider() -> IPIntelligenceProvider:
    path = getattr(
        settings,
        "LOGIN_RISK_IP_PROVIDER",
        "apps.accounts.services.ip_intelligence.OfflineIPIntelligence",
    )
    return import_string(path)()
