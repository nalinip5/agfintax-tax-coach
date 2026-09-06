"""
Verification Agent.

Runs cheap, deterministic checks on a drafted reply before it's sent back
to the user: does it make a numeric claim without a matching tool result,
does it cite something we didn't actually retrieve, does it stray into
professional-judgment territory ("you should...", "this is legal...")
that we want to soften into a referral instead.
"""
import re

_NUMERIC_CLAIM = re.compile(r"\$[\d,]+(\.\d+)?|\b\d{1,3}%\b")
_JUDGMENT_LANGUAGE = re.compile(r"\byou should\b|\bthis is (legal|illegal)\b|\bguaranteed\b", re.I)


def run(draft_reply: str, has_grounding: bool) -> dict:
    issues = []

    if _NUMERIC_CLAIM.search(draft_reply) and not has_grounding:
        issues.append("numeric_claim_without_grounding")

    if _JUDGMENT_LANGUAGE.search(draft_reply):
        issues.append("professional_judgment_language")

    return {"passed": not issues, "issues": issues}
