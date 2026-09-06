import json

from app.agents import verification_agent
from app.tools.llm_client import generate, LLMUnavailableError

_SYSTEM_PROMPT = (
    "You are AGFinTax's tax coach. Answer using ONLY the provided context. "
    "Cite the source domain for any factual claim. Never give definitive legal "
    "advice -- recommend a licensed professional for judgment calls. Be concise."
)


def _deterministic_fallback(intent: str, context: dict) -> str:
    """No LLM configured / call failed -- return a template-based answer
    built directly from tool results so the app still degrades gracefully."""
    if intent == "WHAT_IF" and context.get("scenario", {}).get("ok"):
        r = context["scenario"]["result"]
        return (
            f"For {r['filing_status']} filers in {r['tax_year']} earning "
            f"${r['income']:,.0f}, estimated federal tax is ${r['estimated_federal_tax']:,.2f} "
            f"(effective rate {r['effective_rate']*100:.1f}%)."
        )
    if context.get("rag", {}).get("official_sources"):
        domains = ", ".join(s["domain"] for s in context["rag"]["official_sources"])
        return f"Based on official sources ({domains}), please review the linked guidance for specifics."
    return "I don't have enough information on file to answer that precisely -- could you share more detail?"


def run(intent: str, message: str, context: dict) -> dict:
    prompt = (
        f"User intent: {intent}\nUser message: {message}\n\n"
        f"Available context (tool results):\n{json.dumps(context, default=str)}\n\n"
        "Write the reply to the user now."
    )

    try:
        draft = generate(_SYSTEM_PROMPT, prompt)
    except LLMUnavailableError:
        draft = _deterministic_fallback(intent, context)

    has_grounding = bool(context.get("rag") or context.get("scenario") or context.get("plan"))
    verification = verification_agent.run(draft, has_grounding)

    if not verification["passed"] and "professional_judgment_language" in verification["issues"]:
        draft += "\n\nFor a definitive answer, I'd recommend confirming this with a licensed tax professional."

    citations = [
        {"label": s["domain"], "url": f"https://www.{s['domain']}"}
        for s in context.get("rag", {}).get("official_sources", [])
    ]

    return {"reply": draft, "citations": citations, "verification": verification}
