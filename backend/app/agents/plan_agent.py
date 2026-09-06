from sqlalchemy.orm import Session

from app.tools.tax_plan import get_tax_plan, check_entitlement


def run(db: Session, user_id: str, tax_year: int) -> dict:
    tier = check_entitlement(db, user_id)
    plan = get_tax_plan(db, user_id, tax_year)
    if not plan:
        return {"tier": tier, "found": False, "summary": "No tax plan on file for this year yet."}
    return {
        "tier": tier,
        "found": True,
        "filing_status": plan.filing_status,
        "data": plan.data,
        "strategies": [
            {"title": s.title, "description": s.description, "estimated_savings": s.estimated_savings}
            for s in plan.strategies
        ],
    }
