from __future__ import annotations

import re


SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|api[ _-]?key|access[ _-]?token|token|mfa|otp|recovery[ _-]?code|private[ _-]?security[ _-]?answer)"
    r"(\s*[:=]\s*|\s+(?:is|la|là)\s+)([^\s,;]+)"
)


def redact_sensitive_values(text: str) -> tuple[str, bool]:
    """Redact credential-like values before provider calls or transcript writes."""
    if not isinstance(text, str):
        return str(text), False
    redacted, count = SENSITIVE_VALUE_PATTERN.subn(
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    return redacted, count > 0
