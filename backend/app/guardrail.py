"""
Guardrail Layer.

Deterministic, regex-based PII detection that runs BEFORE any text reaches
the Supervisor or any LLM call. On a match, the message is rejected outright
-- it is never forwarded to an agent, a tool, or the LLM client.
"""
import re
from dataclasses import dataclass


_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "dob": re.compile(r"\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b"),
    "account_number": re.compile(r"\b(?:account|acct)\s*#?\s*\d{6,}\b", re.IGNORECASE),
    "password": re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE),
}


@dataclass
class GuardrailResult:
    blocked: bool
    matched_categories: list[str]


def check_pii(text: str) -> GuardrailResult:
    matched = [name for name, pattern in _PATTERNS.items() if pattern.search(text)]
    return GuardrailResult(blocked=bool(matched), matched_categories=matched)
