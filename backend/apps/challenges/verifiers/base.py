from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class VerificationResult:
    accepted: bool
    feedback: str
    score_delta: int


class BaseVerifier(ABC):
    @abstractmethod
    def verify(
        self, code: str, expected: Optional[str] = None
    ) -> VerificationResult: ...
