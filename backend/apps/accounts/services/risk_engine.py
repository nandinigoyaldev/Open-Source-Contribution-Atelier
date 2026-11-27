"""
Scores how unusual a login is compared with the account's earlier logins.

A signal only fires when the data it needs is present, so an unknown location,
an unknown network or a first ever login adds nothing to the score.
"""

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Sequence

from .ip_intelligence import IPInfo, IPIntelligenceProvider, get_ip_provider

logger = logging.getLogger(__name__)

IMPOSSIBLE_TRAVEL = "impossible_travel"
NEW_PROXY_NETWORK = "new_proxy_network"
NEW_DEVICE = "new_device"

SCORES = {IMPOSSIBLE_TRAVEL: 60, NEW_PROXY_NETWORK: 40, NEW_DEVICE: 20}

MAX_TRAVEL_SPEED_KMH = 800
# IP geolocation is rough, so short hops never count as travel.
MIN_TRAVEL_DISTANCE_KM = 100
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    device_fingerprint: str
    ip_info: IPInfo
    reasons: List[str] = field(default_factory=list)


def device_fingerprint(user_agent: str) -> str:
    """Hash of the user agent without version numbers, so updates do not count."""
    without_versions = re.sub(r"\d+(?:[._]\d+)*", "", user_agent or "")
    normalized = " ".join(without_versions.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    half_lat = (phi2 - phi1) / 2
    half_lon = math.radians(lon2 - lon1) / 2
    a = (
        math.sin(half_lat) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(half_lon) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


class LoginRiskAnalyzer:
    def __init__(self, provider: Optional[IPIntelligenceProvider] = None):
        self.provider = provider

    def lookup(self, ip_address: str) -> IPInfo:
        """Ask the provider. A missing answer or a broken provider means unknown."""
        if not ip_address:
            return IPInfo()
        try:
            provider = self.provider or get_ip_provider()
            return provider.lookup(ip_address) or IPInfo()
        except Exception:
            logger.exception("IP lookup failed, treating the address as unknown")
            return IPInfo()

    def analyze(
        self,
        ip_address: str,
        user_agent: str,
        at: datetime,
        history: Sequence[Any],
    ) -> RiskAssessment:
        """
        Score one login.

        ``history`` holds the account's earlier successful logins, newest first,
        each with ``created_at``, ``latitude``, ``longitude``, ``asn`` and
        ``device_fingerprint``.
        """
        info = self.lookup(ip_address)
        fingerprint = device_fingerprint(user_agent)
        reasons = []

        if self._is_impossible_travel(info, at, history):
            reasons.append(IMPOSSIBLE_TRAVEL)

        known_networks = {past.asn for past in history if past.asn is not None}
        if (
            info.is_proxy
            and info.asn is not None
            and known_networks
            and info.asn not in known_networks
        ):
            reasons.append(NEW_PROXY_NETWORK)

        if history and fingerprint not in {past.device_fingerprint for past in history}:
            reasons.append(NEW_DEVICE)

        return RiskAssessment(
            score=min(100, sum(SCORES[reason] for reason in reasons)),
            device_fingerprint=fingerprint,
            ip_info=info,
            reasons=reasons,
        )

    @staticmethod
    def _is_impossible_travel(info: IPInfo, at: datetime, history) -> bool:
        if info.latitude is None or info.longitude is None:
            return False
        for past in history:
            if past.latitude is None or past.longitude is None:
                continue
            # Only the most recent login with a known position matters.
            distance = distance_km(
                past.latitude, past.longitude, info.latitude, info.longitude
            )
            hours = max((at - past.created_at).total_seconds(), 1) / 3600
            return (
                distance > MIN_TRAVEL_DISTANCE_KM
                and distance / hours > MAX_TRAVEL_SPEED_KMH
            )
        return False
