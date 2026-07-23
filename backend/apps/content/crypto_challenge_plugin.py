"""
Cryptography challenge lesson plugin.

Supports classical cipher exercises: Caesar cipher, Vigenère cipher,
XOR cipher, and hash verification (SHA-256/MD5). Each challenge type
validates a user's submitted plaintext/ciphertext/key against the
expected transformation and awards partial credit for near-misses
where meaningful (e.g. correct algorithm, wrong key).
"""

import hashlib
import string
from typing import Any, Dict, Optional

from .plugins import LessonPlugin, registry


def _caesar_shift(text: str, shift: int) -> str:
    """Apply a Caesar shift to alphabetic characters, preserving case and non-alpha chars."""
    result = []
    for char in text:
        if char.isupper():
            result.append(chr((ord(char) - ord('A') + shift) % 26 + ord('A')))
        elif char.islower():
            result.append(chr((ord(char) - ord('a') + shift) % 26 + ord('a')))
        else:
            result.append(char)
    return "".join(result)


def _vigenere_encode(text: str, key: str) -> str:
    """Encode text using the Vigenère cipher with the given alphabetic key."""
    if not key or not all(c.isalpha() for c in key):
        raise ValueError("Vigenère key must be non-empty and alphabetic")

    key = key.upper()
    result = []
    key_index = 0

    for char in text:
        if char.isalpha():
            shift = ord(key[key_index % len(key)]) - ord('A')
            result.append(_caesar_shift(char, shift))
            key_index += 1
        else:
            result.append(char)

    return "".join(result)


def _vigenere_decode(text: str, key: str) -> str:
    """Decode text using the Vigenère cipher with the given alphabetic key."""
    if not key or not all(c.isalpha() for c in key):
        raise ValueError("Vigenère key must be non-empty and alphabetic")

    key = key.upper()
    result = []
    key_index = 0

    for char in text:
        if char.isalpha():
            shift = -(ord(key[key_index % len(key)]) - ord('A'))
            result.append(_caesar_shift(char, shift))
            key_index += 1
        else:
            result.append(char)

    return "".join(result)


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    """XOR each byte of data with the repeating key."""
    if not key:
        raise ValueError("XOR key must be non-empty")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _hash_matches(plaintext: str, expected_hash: str, algorithm: str) -> bool:
    """Check whether hashing plaintext with the given algorithm produces expected_hash."""
    algorithm = algorithm.lower()
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    hasher = hashlib.new(algorithm)
    hasher.update(plaintext.encode("utf-8"))
    return hasher.hexdigest().lower() == expected_hash.strip().lower()


class CryptographyChallengePlugin(LessonPlugin):
    """
    Lesson plugin for classical cryptography challenges.

    Expected submission data shape:
    {
        "challenge_type": "caesar" | "vigenere" | "xor" | "hash_verify",
        "mode": "encode" | "decode",          # not used for hash_verify
        "input_text": "...",
        "key": "...",                          # shift (int as str) for caesar,
                                                # alphabetic key for vigenere,
                                                # hex-encoded key for xor,
                                                # algorithm name for hash_verify
        "user_answer": "...",                  # what the learner submitted
    }
    """

    identifier = "crypto_challenge"
    version = "1.0"
    name = "Cryptography Challenge"
    description = (
        "Classical cipher and hashing exercises: Caesar, Vigenère, XOR, "
        "and hash verification, with automatic answer validation."
    )

    SUPPORTED_TYPES = {"caesar", "vigenere", "xor", "hash_verify"}

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        base = super().get_metadata()
        base["supported_challenge_types"] = sorted(cls.SUPPORTED_TYPES)
        return base

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        """
        Structural validation only (is the submission well-formed).
        Correctness is evaluated separately in evaluate_progress.
        """
        challenge_type = data.get("challenge_type")
        if challenge_type not in cls.SUPPORTED_TYPES:
            return False

        if "input_text" not in data or not isinstance(data.get("input_text"), str):
            return False

        if "user_answer" not in data or not isinstance(data.get("user_answer"), str):
            return False

        if challenge_type != "hash_verify":
            if data.get("mode") not in ("encode", "decode"):
                return False

        if "key" not in data or not isinstance(data.get("key"), str) or not data["key"]:
            return False

        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        """
        Evaluate correctness of a cryptography challenge submission.
        Returns 100.0 for a fully correct answer, 0.0 for incorrect,
        and partial credit (e.g. 50.0) where the approach is right but
        there's a minor, gradeable mistake (e.g. off-by-one Caesar shift).
        """
        if not cls.validate_submission(data):
            return 0.0

        challenge_type = data["challenge_type"]
        input_text = data["input_text"]
        key = data["key"]
        user_answer = data["user_answer"].strip()

        try:
            if challenge_type == "caesar":
                return cls._evaluate_caesar(input_text, key, data.get("mode"), user_answer)
            elif challenge_type == "vigenere":
                return cls._evaluate_vigenere(input_text, key, data.get("mode"), user_answer)
            elif challenge_type == "xor":
                return cls._evaluate_xor(input_text, key, data.get("mode"), user_answer)
            elif challenge_type == "hash_verify":
                return cls._evaluate_hash_verify(input_text, key, user_answer)
        except ValueError:
            return 0.0

        return 0.0

    @classmethod
    def _evaluate_caesar(cls, input_text: str, key: str, mode: Optional[str], user_answer: str) -> float:
        try:
            shift = int(key)
        except ValueError:
            return 0.0

        if mode == "encode":
            expected = _caesar_shift(input_text, shift)
        elif mode == "decode":
            expected = _caesar_shift(input_text, -shift)
        else:
            return 0.0

        if user_answer == expected:
            return 100.0

        # Partial credit: correct up to case/whitespace mismatch
        if user_answer.strip().lower() == expected.strip().lower():
            return 75.0

        # Partial credit: off-by-one shift (common mistake — inclusive/exclusive
        # shift boundary confusion is a well-known beginner error here)
        for delta in (1, -1):
            near_shift = shift + delta if mode == "encode" else shift - delta
            near_expected = _caesar_shift(input_text, near_shift if mode == "encode" else -near_shift)
            if user_answer == near_expected:
                return 50.0

        return 0.0

    @classmethod
    def _evaluate_vigenere(cls, input_text: str, key: str, mode: Optional[str], user_answer: str) -> float:
        if mode == "encode":
            expected = _vigenere_encode(input_text, key)
        elif mode == "decode":
            expected = _vigenere_decode(input_text, key)
        else:
            return 0.0

        if user_answer == expected:
            return 100.0
        if user_answer.strip().lower() == expected.strip().lower():
            return 75.0
        return 0.0

    @classmethod
    def _evaluate_xor(cls, input_text: str, key: str, mode: Optional[str], user_answer: str) -> float:
        try:
            key_bytes = bytes.fromhex(key)
        except ValueError:
            return 0.0

        if mode == "encode":
            try:
                data_bytes = input_text.encode("utf-8")
                expected_hex = _xor_cipher(data_bytes, key_bytes).hex()
            except ValueError:
                return 0.0
            if user_answer.strip().lower() == expected_hex.lower():
                return 100.0
        elif mode == "decode":
            try:
                input_bytes = bytes.fromhex(input_text)
                expected_plain = _xor_cipher(input_bytes, key_bytes).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                return 0.0
            if user_answer == expected_plain:
                return 100.0
            if user_answer.strip().lower() == expected_plain.strip().lower():
                return 75.0

        return 0.0

    @classmethod
    def _evaluate_hash_verify(cls, input_text: str, algorithm: str, user_answer: str) -> float:
        try:
            matches = _hash_matches(input_text, user_answer, algorithm)
        except ValueError:
            return 0.0
        return 100.0 if matches else 0.0


registry.register(CryptographyChallengePlugin)
