import re

from sqlalchemy.orm import Session

from app.models import Conversation, ConversationTurn, ProfessionalReferral

# PRD 4.5: the exact set of life events Tax Coach must recognize.
_LIFE_EVENT_PATTERNS = {
    "marriage": re.compile(r"\b(married|marriage|wedding|got married)\b", re.IGNORECASE),
    "divorce": re.compile(r"\b(divorce[d]?|separat(ed|ion))\b", re.IGNORECASE),
    "new_child_or_adoption": re.compile(r"\b(had a baby|new (baby|child)|adopt(ed|ion)|pregnant)\b", re.IGNORECASE),
    "home_purchase_or_sale": re.compile(r"\b(bought a house|home purchase|new mortgage|sold (my|our) house|home sale)\b", re.IGNORECASE),
    "job_change_or_new_employer": re.compile(r"\b(new job|laid off|lost my job|changed jobs|new employer|switching jobs)\b", re.IGNORECASE),
    "starting_or_closing_business": re.compile(r"\b(started a business|starting a business|closing (my|the) business|closed my business|sold my business)\b", re.IGNORECASE),
    "retirement": re.compile(r"\b(retir(ed|ing|ement))\b", re.IGNORECASE),
    "inheritance": re.compile(r"\b(inherit(ed|ance)|received an inheritance)\b", re.IGNORECASE),
    "significant_income_change": re.compile(r"\b(income (doubled|dropped|increased|decreased)|big raise|pay cut|lost most of my income)\b", re.IGNORECASE),
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


def get_conversation_history(db: Session, conversation_id: str, limit: int = 15) -> list[ConversationTurn]:
    """PRD 4.9: Tax Coach remembers the last 15 turns of the current
    conversation. Full history beyond that is still retained in the DB
    for audit -- this just bounds how much is used as active context."""
    return (
        db.query(ConversationTurn)
        .filter(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.created_at.desc())
        .limit(limit)
        .all()[::-1]
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
