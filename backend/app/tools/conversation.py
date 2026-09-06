import re

from sqlalchemy.orm import Session

from app.models import Conversation, ConversationTurn, ProfessionalReferral

_LIFE_EVENT_PATTERNS = {
    "marriage": re.compile(r"\b(married|marriage|wedding)\b", re.IGNORECASE),
    "new_child": re.compile(r"\b(had a baby|new (baby|child)|adopt(ed|ion))\b", re.IGNORECASE),
    "job_change": re.compile(r"\b(new job|laid off|lost my job|started a business)\b", re.IGNORECASE),
    "home_purchase": re.compile(r"\b(bought a house|home purchase|new mortgage)\b", re.IGNORECASE),
    "retirement": re.compile(r"\b(retir(ed|ing|ement))\b", re.IGNORECASE),
}


def get_or_create_conversation(db: Session, user_id: str, conversation_id: str | None) -> Conversation:
    if conversation_id:
        convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if convo:
            return convo
    convo = Conversation(user_id=user_id)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


def get_conversation_history(db: Session, conversation_id: str, limit: int = 20) -> list[ConversationTurn]:
    return (
        db.query(ConversationTurn)
        .filter(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.created_at.asc())
        .limit(limit)
        .all()
    )


def add_turn(db: Session, conversation_id: str, role: str, content: str, intent: str | None = None, citations=None):
    turn = ConversationTurn(
        conversation_id=conversation_id,
        role=role,
        content=content,
        intent=intent,
        citations=citations or [],
    )
    db.add(turn)
    db.commit()
    return turn


def detect_life_event(text: str) -> str | None:
    for name, pattern in _LIFE_EVENT_PATTERNS.items():
        if pattern.search(text):
            return name
    return None


def create_professional_referral(db: Session, user_id: str, conversation_id: str | None, reason: str) -> ProfessionalReferral:
    referral = ProfessionalReferral(user_id=user_id, conversation_id=conversation_id, reason=reason)
    db.add(referral)
    db.commit()
    db.refresh(referral)
    return referral
