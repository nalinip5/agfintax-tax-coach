"""
Guardrail Layer.

Deterministic, regex-based PII detection that runs BEFORE any text reaches
the agent, any tool, or any LLM call. On a match, the message is rejected
outright -- it is never forwarded, never stored in conversation history,
and never included in an audit log in raw form.

In addition to blocking, this module produces a MASKED preview of what was
detected (e.g. "***-**-6789") so the user gets clear confirmation of what
tripped the guardrail, without the raw value ever being displayed back,
logged, or persisted anywhere.
"""
import re
from dataclasses import dataclass, field

# Comprehensive PII coverage -- not just the PRD's minimum-required set
# (SSN, credit card, DOB), but the same full set app/tools/pii_scrub.py
# uses for document uploads, so chat and document handling are consistent.
_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    # Catches SSNs the strict format above misses -- e.g. "my ssn is
    # 123-456-7890" (phone-style grouping) or other separators. Any digit
    # sequence near the word "ssn"/"social security" is treated as a match
    # regardless of grouping, since the user has explicitly labeled it.
    "ssn_labeled": re.compile(r"\b(ssn|social security( number)?)\b[^\d]{0,15}\d[\d\-\s]{7,13}\d", re.IGNORECASE),
    "ein": re.compile(r"\b\d{2}-\d{7}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "dob": re.compile(r"\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b"),
    "account_number": re.compile(r"\b(?:account|acct)\b.{0,20}?\d{6,}\b", re.IGNORECASE),
    "routing_number": re.compile(r"\brouting\s*(?:number|#)?\s*[:\-]?\s*\d{9}\b", re.IGNORECASE),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "password": re.compile(r"\bpassword\b\s*(?:is|are|[:=])\s*\S{3,}", re.IGNORECASE),
}


def _mask(category: str, raw_match: str) -> str:
    """Produces a masked preview -- never the raw value -- suitable to
    show the user or write to an audit log."""
    if category == "password":
        return "********"  # never reveal any part of a password
    if category == "email":
        local, _, domain = raw_match.partition("@")
        masked_local = (local[0] + "***") if local else "***"
        return f"{masked_local}@{domain}"

    digits = re.sub(r"\D", "", raw_match)
    if len(digits) <= 4:
        return "*" * len(digits)
    masked_digits = "*" * (len(digits) - 4) + digits[-4:]
    # Re-insert common separators for readability (e.g. ***-**-6789)
    if category in ("ssn", "ssn_labeled") and len(digits) == 9:
        return f"{masked_digits[0:3]}-{masked_digits[3:5]}-{masked_digits[5:9]}"
    return masked_digits


@dataclass
class GuardrailResult:
    blocked: bool
    matched_categories: list[str]
    masked_matches: dict[str, str] = field(default_factory=dict)


def check_pii(text: str) -> GuardrailResult:
    matched = []
    masked = {}
    for name, pattern in _PATTERNS.items():
        m = pattern.search(text)
        if m:
            matched.append(name)
            masked[name] = _mask(name, m.group())
    return GuardrailResult(blocked=bool(matched), matched_categories=matched, masked_matches=masked)
