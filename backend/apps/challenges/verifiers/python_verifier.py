from typing import Optional

from .base import BaseVerifier, VerificationResult


class PythonVerifier(BaseVerifier):
    MIN_CODE_LENGTH = 2

    def verify(self, code: str, expected: Optional[str] = None) -> VerificationResult:
        stripped = code.strip()

        if not stripped:
            return VerificationResult(
                accepted=False, feedback="Code cannot be empty.", score_delta=0
            )

        if len(stripped) < self.MIN_CODE_LENGTH:
            return VerificationResult(
                accepted=False, feedback="Code is too short.", score_delta=0
            )

        syntax_error = self._check_balanced_delimiters(stripped)
        if syntax_error:
            return VerificationResult(
                accepted=False, feedback=syntax_error, score_delta=0
            )

        if expected:
            expected = expected.strip()
            if stripped == expected:
                return VerificationResult(
                    accepted=True,
                    feedback="Correct! Code matches the expected solution.",
                    score_delta=10,
                )
            return VerificationResult(
                accepted=False,
                feedback="Code doesn't match the expected solution.",
                score_delta=0,
            )

        return VerificationResult(
            accepted=True,
            feedback="Python code accepted. Syntax looks valid.",
            score_delta=10,
        )

    def _check_balanced_delimiters(self, code: str) -> Optional[str]:
        pairs = {"{": "}", "(": ")", "[": "]"}
        stack = []
        i = 0
        length = len(code)

        while i < length:
            ch = code[i]

            if ch in ('"', "'"):
                quote = ch
                if i + 2 < length and code[i + 1] == quote and code[i + 2] == quote:
                    i += 3
                    while i + 2 < length:
                        if code[i] == "\\":
                            i += 1
                        elif (
                            code[i] == quote
                            and code[i + 1] == quote
                            and code[i + 2] == quote
                        ):
                            i += 3
                            break
                        i += 1
                    else:
                        i = length
                    continue
                i += 1
                while i < length:
                    if code[i] == "\\":
                        i += 1
                    elif code[i] == quote:
                        break
                    i += 1
                i += 1
                continue

            if ch == "#":
                i += 1
                while i < length and code[i] != "\n":
                    i += 1
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
