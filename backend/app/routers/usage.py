from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.tools.tax_plan import check_entitlement
from app.tools.usage import _TIER_LIMITS, _today
from app.models import UsageDaily, ProfessionalReferral

router = APIRouter()


@router.get("/usage/{user_id}")
def get_usage(user_id: str, db: Session = Depends(get_db)):
    tier = check_entitlement(db, user_id)
    row = db.query(UsageDaily).filter(UsageDaily.user_id == user_id, UsageDaily.date == _today()).first()
    used = row.message_count if row else 0
    return {"tier": tier, "used_today": used, "limit": _TIER_LIMITS.get(tier, 20)}


@router.get("/referrals/{user_id}")
def get_referrals(user_id: str, db: Session = Depends(get_db)):
    rows = db.query(ProfessionalReferral).filter(ProfessionalReferral.user_id == user_id).all()
    return [{"id": r.id, "reason": r.reason, "created_at": r.created_at} for r in rows]
