"""
Orchestration Layer -- Supervisor.

Deterministic, rule-based intent classification (no LLM call). Keeping
routing rule-based means the path a message takes through the system is
auditable and reproducible.
"""
import re
from enum import Enum


class Intent(str, Enum):
    TAX_RULE = "TAX_RULE"
    PLAN_QUESTION = "PLAN_QUESTION"
    STRATEGY_EXPLANATION = "STRATEGY_EXPLANATION"
    WHAT_IF = "WHAT_IF"
    LIFE_EVENT = "LIFE_EVENT"
    PROFESSIONAL_JUDGMENT = "PROFESSIONAL_JUDGMENT"
    DOCUMENTATION = "DOCUMENTATION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    PII_VIOLATION = "PII_VIOLATION"


_RULES: list[tuple[Intent, re.Pattern]] = [
    (Intent.WHAT_IF, re.compile(r"\bwhat if\b|\bwhat would happen\b|\bscenario\b", re.I)),
    (
        Intent.LIFE_EVENT,
        re.compile(r"\b(married|marriage|new (baby|child)|laid off|bought a house|retir(e|ed|ing))\b", re.I),
    ),
    (
        Intent.PROFESSIONAL_JUDGMENT,
        re.compile(r"\b(should i|is it legal|audit risk|represent me|cpa|attorney)\b", re.I),
    ),
    (Intent.PLAN_QUESTION, re.compile(r"\bmy (plan|tax plan|deductions|withholding)\b", re.I)),
    (
        Intent.STRATEGY_EXPLANATION,
        re.compile(r"\b(why|explain|how does).*(strategy|deduction|credit|backdoor|harvest)\b", re.I),
    ),
    (
        Intent.DOCUMENTATION,
        re.compile(r"\b(form \d+|w-?2|1099|schedule [a-z]|irs publication)\b", re.I),
    ),
    (
        Intent.TAX_RULE,
        re.compile(r"\b(tax rate|bracket|deduction|credit|limit|contribution limit|standard deduction)\b", re.I),
    ),
]

_OUT_OF_SCOPE = re.compile(r"\b(weather|sports score|recipe|write me a poem)\b", re.I)


def route(message: str) -> Intent:
    if _OUT_OF_SCOPE.search(message):
        return Intent.OUT_OF_SCOPE
    for intent, pattern in _RULES:
        if pattern.search(message):
            return intent
    return Intent.TAX_RULE  # sensible default for a tax-coach app
