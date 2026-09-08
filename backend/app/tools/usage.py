from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import UsageDaily

_TIER_LIMITS = {
    "none": 0,
    "basic": 20,
    "plus": 100,
    "pro": 1000,
}


def _today() -> str:
    """PRD Section 3: usage limits reset at midnight UTC -- must use UTC
    explicitly, not the server's local timezone."""
    return datetime.now(timezone.utc).date().isoformat()


def check_and_increment(db: Session, user_id: str, tier: str) -> tuple[bool, int, int]:
    """Returns (allowed, used_after_increment, limit)."""
    settings = get_settings()
    limit = _TIER_LIMITS.get(tier, settings.daily_message_limit_default)

    row = (
        db.query(UsageDaily)
        .filter(UsageDaily.user_id == user_id, UsageDaily.date == _today())
        .first()
    )
    if row is None:
        row = UsageDaily(user_id=user_id, date=_today(), message_count=0)
        db.add(row)

    if row.message_count >= limit:
        db.commit()
        return False, row.message_count, limit

    row.message_count += 1
    db.commit()
    return True, row.message_count, limit
