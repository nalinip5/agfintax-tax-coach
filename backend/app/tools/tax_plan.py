from sqlalchemy.orm import Session

from app.models import Subscription, TaxPlan


def get_tax_plan(db: Session, user_id: str, tax_year: int) -> TaxPlan | None:
    return (
        db.query(TaxPlan)
        .filter(TaxPlan.user_id == user_id, TaxPlan.tax_year == tax_year)
        .first()
    )


def get_latest_tax_plan(db: Session, user_id: str) -> TaxPlan | None:
    """Returns the user's most recent plan by tax_year, regardless of the
    current calendar date. A 'current' tax plan is whichever year's plan
    is active for the user -- not necessarily the calendar year (tax
    planning for a given year commonly continues well into the next
    calendar year)."""
    return (
        db.query(TaxPlan)
        .filter(TaxPlan.user_id == user_id)
        .order_by(TaxPlan.tax_year.desc())
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
