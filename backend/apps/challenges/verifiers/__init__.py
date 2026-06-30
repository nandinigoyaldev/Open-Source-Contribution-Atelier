from typing import List, Optional

from .base import BaseVerifier
from .python_verifier import PythonVerifier
from .rust_verifier import RustVerifier

VERIFIERS = {
    "python": PythonVerifier(),
    "rust": RustVerifier(),
}


def get_verifier(language: str) -> Optional[BaseVerifier]:
    return VERIFIERS.get(language.lower())


def get_supported_languages() -> List[str]:
    return list(VERIFIERS.keys())


__all__ = [
    "BaseVerifier",
    "PythonVerifier",
    "RustVerifier",
    "VerificationResult",
    "get_verifier",
    "get_supported_languages",
]
