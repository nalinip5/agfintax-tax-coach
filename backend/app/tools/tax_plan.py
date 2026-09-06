from sqlalchemy.orm import Session

from app.models import Subscription, TaxPlan


def get_tax_plan(db: Session, user_id: str, tax_year: int) -> TaxPlan | None:
    return (
        db.query(TaxPlan)
        .filter(TaxPlan.user_id == user_id, TaxPlan.tax_year == tax_year)
        .first()
    )


def check_entitlement(db: Session, user_id: str) -> str:
    """Returns the subscriber's active tier, or 'none' if unsubscribed."""
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id, Subscription.is_active.is_(True))
        .order_by(Subscription.started_at.desc())
        .first()
    )
    return sub.tier if sub else "none"
