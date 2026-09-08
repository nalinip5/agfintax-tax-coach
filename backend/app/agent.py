"""
Single-agent, deterministic tool-calling pipeline for AGFinTax Tax Coach
-- no LLM anywhere in this path. Implements the functional requirements
in AGFinTax-TaxCoach-ProductRequirements-01092026.md:

  4.1 plan-aware conversation      4.6 what-if scenarios (subset)
  4.2 plain-English answers        4.7 (suggestions -- see routers/plan.py)
  4.3 verified IRS constants only  4.8 PII guardrail (see app/guardrail.py)
  4.4 official IRS source search   4.9 last-15-turns continuity
  4.5 life event impact            4.10 professional referral

Rule-based intent detection decides which tool(s) to call; a template
composes the final reply directly from tool results. This keeps the
"agentic pipeline calling external + internal tools" shape (Tavily
discovery, real page-content extraction from the PRD's approved-domains-
only registry, deterministic tax math grounded in verified constants)
while adding zero LLM cost/latency/dependency. A genuine MCP server/client
pair (app/mcp_server.py, app/mcp_client.py) exposes these same tools over
the real Model Context Protocol for any MCP host that wants LLM-driven
tool selection instead -- not wired into this default path per explicit
instruction to avoid an LLM here.
"""
import datetime
import re

from sqlalchemy.orm import Session

from app.tools.knowledge import search_internal_knowledge, search_official_sources
from app.tools.tax_calc import calculate_tax_scenario, get_tax_constant
from app.tools.tax_plan import get_tax_plan, get_latest_tax_plan, check_entitlement
from app.tools.conversation import detect_life_event, create_professional_referral, get_conversation_history

REFERRAL_CTA = "Talk to our AGFinTax Tax Planner"

# --- PRD Section 7: explicitly out of scope, regardless of phrasing ---
_OUT_OF_SCOPE = re.compile(
    r"\b(weather|sports score|recipe|write me a poem|"
    r"buy|sell|hold\b.*(stock|shares|crypto|bitcoin)|portfolio alloc|"
    r"interpret (this|my) (contract|will|trust)|legal advice|"
    r"state tax|state return|"
    r"corporate (tax|return)|partnership return|trust return|"
    r"file my (return|taxes)|prepare my (return|taxes)|submit my (return|taxes))\b",
    re.I,
)

# PRD 4.10: never make election decisions -- redirect professional-judgment asks.
_PROFESSIONAL_JUDGMENT = re.compile(
    r"\b(should i elect|should i choose|should i take|which (strategy|option) should i|"
    r"what would you (do|recommend)|do you recommend|is it (better|worth it) (for me )?to)\b",
    re.I,
)

_WHAT_IF = re.compile(r"\bwhat if\b|\bwhat would happen\b|\bscenario\b", re.I)
_PLAN_QUESTION = re.compile(r"\bmy (plan|tax plan|deductions|withholding|strategies|savings)\b", re.I)
_CHARITABLE = re.compile(r"\bcharitable donation|\bdonate\b|\bcharity\b", re.I)
_SEP_IRA = re.compile(r"\bsep[- ]?ira\b", re.I)

_DOUBLE_PATTERN = re.compile(r"\b(doubl(e|es|ed))\b", re.I)
_HALVE_PATTERN = re.compile(r"\b(halv(e|es|ed)|cut in half)\b", re.I)
_ADDITIVE_UP_PATTERN = re.compile(r"(?:raise|increase|bonus|extra|more) of\s*\$?([\d,]+)|(?:get|got|receive[ds]?) a\s*\$?([\d,]+)\s*(?:raise|bonus)", re.I)
_ADDITIVE_DOWN_PATTERN = re.compile(r"(?:pay cut|decrease|lose|lost|less) of\s*\$?([\d,]+)|(?:take|took) a\s*\$?([\d,]+)\s*(?:pay cut|cut)", re.I)
_PERCENT_PATTERN = re.compile(r"(increase|decrease|drop|grow|go up|go down)s?\s*(?:by)?\s*(\d+)\s*%|(\d+)\s*%\s*(increase|decrease|more|less)", re.I)


def _resolve_scenario_income(message: str, base_agi: float | None, default: float = 90000) -> float:
    """PRD 4.6: what-if math must be grounded in the user's ACTUAL plan
    data, never an invented flat number -- so relative language ('doubles',
    'a $10,000 raise', 'drops 20%') must be resolved against their real
    AGI, not treated as if it were the absolute new income."""
    base = base_agi if base_agi is not None else default

    if _DOUBLE_PATTERN.search(message):
        return base * 2
    if _HALVE_PATTERN.search(message):
        return base / 2

    m = _ADDITIVE_UP_PATTERN.search(message)
    if m:
        amount = float((m.group(1) or m.group(2)).replace(",", ""))
        return base + amount

    m = _ADDITIVE_DOWN_PATTERN.search(message)
    if m:
        amount = float((m.group(1) or m.group(2)).replace(",", ""))
        return max(base - amount, 0)

    m = _PERCENT_PATTERN.search(message)
    if m:
        direction = (m.group(1) or m.group(4) or "").lower()
        pct = float(m.group(2) or m.group(3))
        sign = -1 if direction in ("decrease", "drop", "less", "go down") else 1
        return max(base * (1 + sign * pct / 100), 0)

    # Falls through to an absolute dollar figure in the message (e.g.
    # "what if I earn $200,000") -- that IS the intended new total income.
    return _extract_income(message, default=base)


_INCOME_PATTERN = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(k\b)?", re.I)

# PRD 4.3: constants Tax Coach must answer from the verified DB, never
# estimate. Keyword -> (constant key, needs filing_status, friendly label).
_CONSTANT_KEYWORDS: list[tuple[re.Pattern, str, bool, str]] = [
    (re.compile(r"\bsep[- ]?ira\b.*\b(limit|contribution)\b|\b(limit|contribution)\b.*\bsep[- ]?ira\b", re.I), "sep_ira_contribution_limit", False, "SEP-IRA contribution limit"),
    (re.compile(r"\broth ira\b.*(phaseout|phase.out|income limit)|\b(phaseout|phase.out)\b.*\broth\b", re.I), "roth_ira_phaseout_start", True, "Roth IRA income phaseout"),
    (re.compile(r"\bhsa\b.*(limit|contribution)|\bcontribution\b.*\bhsa\b", re.I), "hsa_contribution_limit_self_only", False, "HSA contribution limit"),
    (re.compile(r"\bsalt\b.*(cap|limit|deduction)|\bstate and local tax\b", re.I), "salt_deduction_cap", False, "SALT deduction cap"),
    (re.compile(r"\bniit\b|net investment income tax", re.I), "niit_threshold", True, "Net Investment Income Tax threshold"),
    (re.compile(r"\bqbi\b|qualified business income", re.I), "qbi_deduction_income_threshold", True, "QBI deduction income threshold"),
    (re.compile(r"\b401\(?k\)?\b.*(limit|contribution)(?!.*catch)", re.I), "401k_employee_contribution_limit", False, "401(k) employee contribution limit"),
    (re.compile(r"\b401\(?k\)?\b.*catch.?up", re.I), "401k_catchup_contribution_50plus", False, "401(k) catch-up contribution (age 50+)"),
    (re.compile(r"\bira\b.*catch.?up", re.I), "ira_catchup_contribution_50plus", False, "IRA catch-up contribution (age 50+)"),
    (re.compile(r"\b(?<!sep.)(?<!roth )ira\b.*(limit|contribution)", re.I), "ira_contribution_limit", False, "IRA contribution limit"),
    (re.compile(r"standard deduction", re.I), "standard_deduction", True, "standard deduction"),
    (re.compile(r"child tax credit", re.I), "child_tax_credit_per_child", False, "Child Tax Credit"),
]


def _lookup_constant(db: Session, message: str, tax_year: int, filing_status: str) -> tuple[str, list[dict]] | None:
    """PRD 4.3: if the question matches a known IRS-defined constant,
    answer with the exact verified figure -- never fall through to a
    fuzzy RAG search for these. Returns None if no constant keyword matched."""
    for pattern, key, needs_status, label in _CONSTANT_KEYWORDS:
        if not pattern.search(message):
            continue
        value, actual_year = get_tax_constant(db, tax_year, key, filing_status if needs_status else None)
        if value is None:
            return (
                f"I don't have a verified {label} figure on file for {tax_year} yet -- I won't guess at "
                f"that number. {REFERRAL_CTA} can confirm the current figure.",
                [],
            )
        status_note = f" ({filing_status.replace('_', ' ')})" if needs_status else ""
        reply = f"The {label} for {actual_year}{status_note} is ${value:,.0f}, per IRS.gov."
        return reply, [{"label": "irs.gov", "url": "https://www.irs.gov"}]
    return None


def _extract_income(message: str, default: float = 90000) -> float:
    """Best-effort deterministic extraction of a dollar figure -- no LLM
    entity extraction (PRD: estimates must never be invented)."""
    for match in _INCOME_PATTERN.finditer(message):
        raw, k_suffix = match.groups()
        if not raw:
            continue
        value = float(raw.replace(",", ""))
        if value < 10 and not k_suffix:
            continue
        if 1900 <= value <= 2100 and not k_suffix:  # skip things that look like a year
            continue
        return value * 1000 if k_suffix else value
    return default


def _scope_tags_for(message: str) -> list[str]:
    lowered = message.lower()
    tags = []
    if any(w in lowered for w in ["401k", "ira", "retirement", "roth", "sep-ira", "sep ira", "pension"]):
        tags.append("retirement")
    if any(w in lowered for w in ["llc", "self-employed", "schedule c", "business", "1099"]):
        tags.append("business")
    if any(w in lowered for w in ["mortgage", "rental", "home sale", "real estate"]):
        tags.append("real_estate")
    if any(w in lowered for w in ["bill", "act", "law", "legislation", "obbba"]):
        tags.append("legislation")
    return tags


def _compose_from_sources(sources: list[dict], intro: str) -> tuple[str, list[dict]]:
    """PRD 4.4: every answer sourced from an official domain must include
    that source's URL so the user can verify it themselves."""
    if not sources:
        return (
            f"{intro} I wasn't able to retrieve the exact figure from an official source just now. "
            f"I don't want to guess at a specific number -- please try again shortly, or {REFERRAL_CTA} "
            f"can pull this for you directly.",
            [],
        )

    top = sources[0]
    content = (top.get("content") or "").strip()
    snippet = content[:400] + ("..." if len(content) > 400 else "") if content else top.get("title", "")

    reply = f"{intro} According to {top['domain']}: {snippet}"
    if len(sources) > 1:
        others = ", ".join(s["domain"] for s in sources[1:3])
        reply += f"\n\nAlso worth checking: {others}."

    citations = [{"label": s["domain"], "url": s.get("url") or f"https://www.{s['domain']}"} for s in sources[:3]]
    return reply, citations


def _get_current_plan(db: Session, user_id: str):
    """The user's active tax plan -- whichever year is most recent for
    them, not necessarily the calendar year (see get_latest_tax_plan)."""
    return get_latest_tax_plan(db, user_id)


def _plan_summary(plan) -> str:
    """PRD 4.1: filing status, AGI/MAGI/marginal rate, savings, strategies."""
    parts = [f"{plan.filing_status} filer, AGI ${plan.agi:,.0f}" if plan.agi else plan.filing_status]
    if plan.magi:
        parts.append(f"MAGI ${plan.magi:,.0f}")
    if plan.marginal_rate:
        parts.append(f"{plan.marginal_rate*100:.0f}% marginal bracket")
    summary = ", ".join(parts) + "."
    if plan.confirmed_savings or plan.potential_savings:
        summary += f" Confirmed savings so far: ${plan.confirmed_savings:,.0f}; potential additional savings identified: ${plan.potential_savings:,.0f}."
    return summary


def _relevant_strategies(plan, keywords: list[str]) -> list:
    if not keywords:
        return list(plan.strategies)
    return [
        s for s in plan.strategies
        if any(k.lower() in (s.title + " " + s.description).lower() for k in keywords)
    ] or list(plan.strategies)


_LIFE_EVENT_CONSTANTS: dict[str, list[tuple[str, bool]]] = {
    "marriage": [("standard_deduction", True)],
    "divorce": [("standard_deduction", True)],
    "new_child_or_adoption": [("child_tax_credit_per_child", False)],
    "retirement": [("ira_contribution_limit", False), ("401k_employee_contribution_limit", False)],
    "job_change_or_new_employer": [("401k_employee_contribution_limit", False)],
    "starting_or_closing_business": [("sep_ira_contribution_limit", False)],
    "significant_income_change": [("niit_threshold", True)],
}


def _life_event_constant_note(db: Session, life_event: str, tax_year: int, filing_status: str) -> str:
    """PRD 4.5: life event handling must fetch the applicable tax
    constants, not just narrative guidance."""
    entries = _LIFE_EVENT_CONSTANTS.get(life_event, [])
    notes = []
    for key, needs_status in entries:
        value, actual_year = get_tax_constant(db, tax_year, key, filing_status if needs_status else None)
        if value is not None:
            label = key.replace("_", " ")
            notes.append(f"{label} ({actual_year}): ${value:,.0f}")
    return " Relevant figures: " + "; ".join(notes) + "." if notes else ""


def run(db: Session, user_id: str, conversation_id: str, message: str) -> dict:
    """Entry point: eligibility gate -> rule-based intent -> tool call(s)
    -> templated reply. Returns {reply, citations}."""

    # --- PRD Section 3: paid subscribers with a completed plan only ---
    tier = check_entitlement(db, user_id)
    if tier in (None, "none"):
        return {
            "reply": (
                f"Tax Coach is available to paid AGFinTax subscribers who have completed their tax "
                f"plan. {REFERRAL_CTA} to get started."
            ),
            "citations": [],
        }

    plan = _get_current_plan(db, user_id)
    if plan is None:
        return {
            "reply": (
                f"I don't see a completed tax plan on file for you yet -- Tax Coach needs your "
                f"intake and plan results to give you personalized, accurate answers. Please complete "
                f"your questionnaire and run your plan first, then come back and ask me anything."
            ),
            "citations": [],
        }

    # Pulled for continuity/audit per PRD 4.9; deterministic replies don't
    # need it to change content, but a real conversational agent would use
    # it to avoid asking the user to repeat themselves.
    _history = get_conversation_history(db, conversation_id, limit=15)

    if _OUT_OF_SCOPE.search(message):
        return {
            "reply": (
                "That's outside what Tax Coach can help with -- I'm scoped to your federal individual "
                f"tax plan only (not investing, legal matters, state taxes, business entity returns, or "
                f"filing your return). {REFERRAL_CTA} for anything outside that."
            ),
            "citations": [],
        }

    if _PROFESSIONAL_JUDGMENT.search(message):
        create_professional_referral(db, user_id, conversation_id, reason="Professional-judgment question")
        return {
            "reply": (
                "I can explain how a strategy works, calculate the numbers, and cite the official rules "
                f"-- but electing or skipping a strategy is a decision for you and a licensed professional "
                f"together, not something I can decide for you. {REFERRAL_CTA} to talk through this decision."
            ),
            "citations": [],
        }

    scope_tags = _scope_tags_for(message)

    # --- Life event (PRD 4.5): identify -> IRS guidance -> tax constants
    # -> personalized impact -> relevant plan strategies -> referral. ---
    life_event = detect_life_event(message)
    if life_event:
        create_professional_referral(db, user_id, conversation_id, reason=f"Life event: {life_event}")
        sources = search_official_sources(db, scope_tags or ["general"], tier, query=f"{life_event.replace('_', ' ')} tax impact")
        label = life_event.replace("_", " ")
        relevant = _relevant_strategies(plan, scope_tags)
        strategy_note = ""
        if relevant:
            titles = ", ".join(s.title for s in relevant[:2])
            strategy_note = f" This may also change the relevance of strategies already on your plan, including: {titles}."

        reply = (
            f"I see this involves {label} -- events like this typically affect your filing status, "
            f"withholding, and which deductions or credits you qualify for. Based on your current plan "
            f"({_plan_summary(plan)}), this is worth reviewing closely.{strategy_note}"
            f"{_life_event_constant_note(db, life_event, plan.tax_year, plan.filing_status)}\n\n"
        )
        if sources:
            reply += f"Relevant guidance from {sources[0]['domain']}: {(sources[0].get('content') or '')[:300]}\n\n"
        reply += f"{REFERRAL_CTA} to update your plan for this change."
        citations = [{"label": s["domain"], "url": s.get("url") or f"https://www.{s['domain']}"} for s in sources[:2]]
        return {"reply": reply, "citations": citations}

    # --- What-if scenarios (PRD 4.6): grounded in verified constants AND
    # the user's actual plan data -- never invented. ---
    if _WHAT_IF.search(message):
        if _SEP_IRA.search(message):
            limit_value, limit_year = get_tax_constant(db, plan.tax_year, "sep_ira_contribution_limit")
            if limit_value and plan.agi:
                new_agi = max(plan.agi - limit_value, 0)
                try:
                    before = calculate_tax_scenario(db, plan.tax_year, plan.filing_status, plan.agi)
                    after = calculate_tax_scenario(db, plan.tax_year, plan.filing_status, new_agi)
                    savings = before["estimated_federal_tax"] - after["estimated_federal_tax"]
                    reply = (
                        f"Maxing out a SEP-IRA contribution (limit: ${limit_value:,.0f} for {limit_year}) would "
                        f"lower your AGI from ${plan.agi:,.0f} to ${new_agi:,.0f}, reducing your estimated "
                        f"federal tax by about ${savings:,.2f} (from ${before['estimated_federal_tax']:,.2f} to "
                        f"${after['estimated_federal_tax']:,.2f})."
                    )
                    return {"reply": reply, "citations": [{"label": "irs.gov", "url": "https://www.irs.gov"}]}
                except ValueError:
                    pass
            return {"reply": "I don't have enough plan or constant data on file to calculate that precisely right now.", "citations": []}

        if _CHARITABLE.search(message):
            std_ded, std_year = get_tax_constant(db, plan.tax_year, "standard_deduction", plan.filing_status)
            income = _extract_income(message, default=0)
            if std_ded and income:
                reply = (
                    f"A ${income:,.0f} charitable donation only reduces your tax if your itemized deductions "
                    f"(including this donation) exceed your standard deduction of ${std_ded:,.0f} ({std_year}, "
                    f"{plan.filing_status}). If they don't, the donation doesn't change your federal tax this "
                    f"year under current law. I don't have your other itemizable deductions on file to compare -- "
                    f"{REFERRAL_CTA} can run the full comparison against your plan."
                )
                return {"reply": reply, "citations": [{"label": "irs.gov", "url": "https://www.irs.gov"}]}

        # Default what-if: income change, grounded in real bracket math and
        # the plan's actual AGI -- resolves relative language ('doubles',
        # 'a $10,000 raise', '20% drop') against it rather than a flat guess.
        income = _resolve_scenario_income(message, plan.agi)
        try:
            result = calculate_tax_scenario(db, plan.tax_year, plan.filing_status, income)
            year_note = (
                f" (using the most recent published bracket table, {result['tax_year']}, since "
                f"{result['requested_tax_year']} isn't published yet)"
                if result["used_prior_year_brackets"] else ""
            )
            reply = (
                f"For a {plan.filing_status} filer earning ${result['income']:,.0f}, estimated federal tax is "
                f"${result['estimated_federal_tax']:,.2f} (effective rate {result['effective_rate']*100:.1f}%)"
                f"{year_note}."
            )
            return {"reply": reply, "citations": []}
        except ValueError:
            sources = search_official_sources(db, scope_tags, tier, query=message)
            reply, citations = _compose_from_sources(sources, "I don't have bracket data for that scenario on file, but here's relevant guidance:")
            return {"reply": reply, "citations": citations}

    # --- Plan question (PRD 4.1): answer from the user's actual plan. ---
    if _PLAN_QUESTION.search(message):
        strategies_text = "\n".join(
            f"- {s.title} ({s.status}, est. ${s.estimated_savings:,.0f}): {s.why_it_applies or s.description}"
            for s in plan.strategies
        ) or "No strategies identified yet."
        reply = f"{_plan_summary(plan)}\n\nStrategies on your plan:\n{strategies_text}"
        if plan.urgent_observations:
            reply += "\n\nWorth your attention: " + "; ".join(plan.urgent_observations)
        return {"reply": reply, "citations": []}

    # --- Direct IRS constant lookup (PRD 4.3) -- checked before any RAG
    # fallback, since these must be answered from the verified DB exactly. ---
    constant_answer = _lookup_constant(db, message, plan.tax_year, plan.filing_status)
    if constant_answer:
        reply, citations = constant_answer
        return {"reply": reply, "citations": citations}

    # --- Default: internal knowledge first, then live official sources. ---
    internal_hits = search_internal_knowledge(db, message)
    if internal_hits:
        content = internal_hits[0]["content"][:400]
        return {"reply": f"From verified internal guidance: {content}", "citations": []}

    sources = search_official_sources(db, scope_tags, tier, query=message)
    reply, citations = _compose_from_sources(sources, "Here's what I found:")
    return {"reply": reply, "citations": citations}
