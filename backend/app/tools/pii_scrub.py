"""
PII scrubbing for uploaded/OCR'd document text.

Distinct from app/guardrail.py (which BLOCKS a chat message outright on a
PII match). Here the goal is different: a user-uploaded document (W-2,
1099, bank statement) will legitimately contain SSNs, account numbers,
etc., and we still want to let them upload it -- but the raw, unscrubbed
text must never be persisted, ingested for RAG, or handed to an LLM.
Only the scrubbed text is allowed past this module.
"""
import re
from dataclasses import dataclass, field

_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    "ssn_labeled": re.compile(r"\b(ssn|social security( number)?)\b[^\d]{0,15}\d[\d\-\s]{7,13}\d", re.IGNORECASE),
    "ein": re.compile(r"\b\d{2}-\d{7}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "dob": re.compile(r"\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b"),
    "account_number": re.compile(r"\b(?:account|acct)\s*#?\s*[:\-]?\s*\d{6,}\b", re.IGNORECASE),
    "routing_number": re.compile(r"\b\d{9}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "password": re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE),
}


@dataclass
class ScrubResult:
    scrubbed_text: str
    redacted_categories: list[str] = field(default_factory=list)
    redaction_count: int = 0


def scrub_pii(text: str) -> ScrubResult:
    """Redacts PII in place, returning the scrubbed text plus which
    categories were found. Never returns or logs the original matches."""
    redacted_categories: list[str] = []
    count = 0

    def _redact(pattern_name: str, pattern: re.Pattern, s: str) -> str:
        nonlocal count
        def _sub(m: re.Match) -> str:
            nonlocal count
            count += 1
            return f"[REDACTED_{pattern_name.upper()}]"
        new_s, n = pattern.subn(_sub, s)
        if n:
            redacted_categories.append(pattern_name)
        return new_s

    scrubbed = text
    for name, pattern in _PATTERNS.items():
        scrubbed = _redact(name, pattern, scrubbed)

    return ScrubResult(scrubbed_text=scrubbed, redacted_categories=redacted_categories, redaction_count=count)
