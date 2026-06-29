import re
from typing import Optional

from .base import BaseVerifier, VerificationResult


class RustVerifier(BaseVerifier):
    MIN_CODE_LENGTH = 3

    def verify(self, code: str, expected: Optional[str] = None) -> VerificationResult:
        stripped = code.strip()

        if not stripped:
            return VerificationResult(
                accepted=False,
                feedback="Code cannot be empty.",
                score_delta=0,
            )

        if len(stripped) < self.MIN_CODE_LENGTH:
            return VerificationResult(
                accepted=False,
                feedback="Code is too short to be valid Rust.",
                score_delta=0,
            )

        syntax_error = self._check_balanced_delimiters(stripped)
        if syntax_error:
            return VerificationResult(
                accepted=False,
                feedback=syntax_error,
                score_delta=0,
            )

        if expected:
            expected = expected.strip()
            if stripped == expected:
                return VerificationResult(
                    accepted=True,
                    feedback="Correct! Your Rust code matches the expected solution.",
                    score_delta=10,
                )

            if self._structurally_matches(stripped, expected):
                return VerificationResult(
                    accepted=False,
                    feedback="Close! Your code is structurally similar but not an exact match.",
                    score_delta=5,
                )

            return VerificationResult(
                accepted=False,
                feedback="Your Rust code doesn't match the expected solution. Check the hint and try again.",
                score_delta=0,
            )

        return VerificationResult(
            accepted=True,
            feedback="Rust code accepted. Syntax looks valid.",
            score_delta=10,
        )

    def _check_balanced_delimiters(self, code: str) -> Optional[str]:
        pairs = {"{": "}", "(": ")", "[": "]"}
        stack = []
        i = 0
        length = len(code)

        while i < length:
            ch = code[i]

            if ch == '"':
                i += 1
                while i < length:
                    if code[i] == "\\":
                        i += 1
                    elif code[i] == '"':
                        break
                    i += 1
                i += 1
                continue

            if ch == "'":
                i += 1
                if i < length and code[i] == "\\":
                    i += 1
                if i < length:
                    i += 1
                i += 1
                continue

            if ch == "/" and i + 1 < length:
                if code[i + 1] == "/":
                    i += 2
                    while i < length and code[i] != "\n":
                        i += 1
                    continue
                if code[i + 1] == "*":
                    i += 2
                    while i + 1 < length:
                        if code[i] == "*" and code[i + 1] == "/":
                            i += 2
                            break
                        i += 1
                    else:
                        return "Unclosed block comment."
                    continue

            if ch in pairs:
                stack.append((ch, i + 1))
            elif ch in pairs.values():
                if not stack:
                    return f"Unexpected closing delimiter '{ch}' at position {i + 1}."
                opening, line = stack.pop()
                if pairs[opening] != ch:
                    return f"Mismatched delimiter '{opening}' at position {line} with '{ch}' at position {i + 1}."

            i += 1

        if stack:
            opening, line = stack[0]
            return f"Unclosed delimiter '{opening}' opened at position {line}."

        return None

    def _structurally_matches(self, code: str, expected: str) -> bool:
        code_normalized = re.sub(r"\s+", " ", code).strip()
        expected_normalized = re.sub(r"\s+", " ", expected).strip()
        if code_normalized == expected_normalized:
            return True
        code_clean = re.sub(r"\b[a-zA-Z_]\w*\b", "X", code_normalized)
        expected_clean = re.sub(r"\b[a-zA-Z_]\w*\b", "X", expected_normalized)
        return code_clean == expected_clean
