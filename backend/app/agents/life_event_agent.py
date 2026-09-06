from sqlalchemy.orm import Session

from app.tools.conversation import detect_life_event, create_professional_referral

_ALWAYS_REFER = {"retirement", "job_change"}


def run(db: Session, user_id: str, conversation_id: str, message: str) -> dict:
    event = detect_life_event(message)
    referred = False
    if event in _ALWAYS_REFER:
        create_professional_referral(
            db, user_id, conversation_id, reason=f"Life event '{event}' may need professional review"
        )
        referred = True
    return {"life_event": event, "referred_to_professional": referred}
