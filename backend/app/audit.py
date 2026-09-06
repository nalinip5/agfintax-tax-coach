from sqlalchemy.orm import Session

from app.models import AuditEvent


def log_event(
    db: Session,
    event_type: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        conversation_id=conversation_id,
        payload=payload or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
