import re
from dataclasses import dataclass, field


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
API_KEY_RE = re.compile(r"\b(?:api[_-]?key|access[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{8,}['\"]?", re.IGNORECASE)
PASSWORD_RE = re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?[^\s,'\"]{4,}['\"]?", re.IGNORECASE)
COOKIE_RE = re.compile(r"\b(?:cookie|session(?:id)?|set-cookie)\s*[:=]\s*[^\n;]+", re.IGNORECASE)
INTERNAL_IP_RE = re.compile(r"\b(?:(?:10)\.\d{1,3}\.\d{1,3}\.\d{1,3}|(?:192\.168)\.\d{1,3}\.\d{1,3}|(?:172\.(?:1[6-9]|2\d|3[0-1]))\.\d{1,3}\.\d{1,3})\b")


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def redacted(self) -> bool:
        return any(self.counts.values())


def _replace(pattern: re.Pattern[str], text: str, label: str, counts: dict[str, int]) -> str:
    matches = pattern.findall(text)
    counts[label] = len(matches)
    return pattern.sub(f"[REDACTED_{label.upper()}]", text)


def redact_text(text: str, redact_internal_ips: bool = True) -> RedactionResult:
    counts: dict[str, int] = {}
    value = text
    for label, pattern in [
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("bearer_token", BEARER_RE),
        ("jwt", JWT_RE),
        ("api_key", API_KEY_RE),
        ("password", PASSWORD_RE),
        ("cookie", COOKIE_RE),
    ]:
        value = _replace(pattern, value, label, counts)
    if redact_internal_ips:
        value = _replace(INTERNAL_IP_RE, value, "internal_ip", counts)
    return RedactionResult(text=value, counts=counts)
