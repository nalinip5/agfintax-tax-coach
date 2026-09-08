from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ScenarioRequest
from app.tools.tax_plan import get_tax_plan, get_latest_tax_plan, check_entitlement
from app.tools.tax_calc import calculate_tax_scenario
from datetime import date

router = APIRouter()


@router.get("/tax-plan/{user_id}/{tax_year}")
def get_plan(user_id: str, tax_year: int, db: Session = Depends(get_db)):
    tier = check_entitlement(db, user_id)
    plan = get_tax_plan(db, user_id, tax_year)
    if not plan:
        return {"tier": tier, "found": False, "summary": "No tax plan on file for this year yet."}
    return {
        "tier": tier,
        "found": True,
        "filing_status": plan.filing_status,
        "data": plan.data,
        "agi": plan.agi,
        "magi": plan.magi,
        "marginal_rate": plan.marginal_rate,
        "confirmed_savings": plan.confirmed_savings,
        "potential_savings": plan.potential_savings,
        "urgent_observations": plan.urgent_observations,
        "missing_questionnaire_items": plan.missing_questionnaire_items,
        "strategies": [
            {
                "title": s.title,
                "description": s.description,
                "why_it_applies": s.why_it_applies,
                "status": s.status,
                "estimated_savings": s.estimated_savings,
            }
            for s in plan.strategies
        ],
    }


@router.get("/suggestions/{user_id}")
def get_suggestions(user_id: str, db: Session = Depends(get_db)):
    """PRD 4.7: contextual conversation starters reflecting the user's
    actual plan -- never generic prompts like 'ask me anything'."""
    plan = get_latest_tax_plan(db, user_id)
    if not plan:
        return {"suggestions": []}

    suggestions: list[str] = []

    for obs in (plan.urgent_observations or [])[:1]:
        suggestions.append(f"What should I do about: {obs}?")

    if plan.magi:
        # Flag proximity to well-known thresholds (NIIT, IRMAA, Roth phaseout).
        thresholds = {
            "the Net Investment Income Tax threshold": 200000 if plan.filing_status == "single" else 250000,
            "Medicare IRMAA surcharge thresholds": 106000 if plan.filing_status == "single" else 212000,
        }
        for label, value in thresholds.items():
            if abs(plan.magi - value) <= 15000:
                suggestions.append(f"How close am I to {label}, and what happens if I cross it?")
                break

    top_strategy = max(plan.strategies, key=lambda s: s.estimated_savings or 0, default=None)
    if top_strategy:
        suggestions.append(f"Why does '{top_strategy.title}' apply to me, and how much could it save?")

    statuses = {s.status for s in plan.strategies}
    if "potential" in statuses:
        suggestions.append("What do I need to do to confirm my potential savings strategies?")

    if not suggestions:
        suggestions = [f"What strategies are on my {plan.tax_year} plan?"]

    return {"suggestions": suggestions[:4]}


@router.post("/scenarios")
def run_scenario(req: ScenarioRequest, db: Session = Depends(get_db)):
    income = req.changes.get("income", 0)
    try:
        return {"ok": True, "result": calculate_tax_scenario(db, req.tax_year, req.filing_status, income)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
