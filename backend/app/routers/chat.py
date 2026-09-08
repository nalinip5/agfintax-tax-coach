from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth import get_current_user_id
from app.db import get_db
from app.guardrail import check_pii
from app.schemas import ChatRequest, ChatResponse, Citation
from app.tools.tax_plan import check_entitlement
from app.tools.usage import check_and_increment
from app.tools.conversation import get_or_create_conversation, add_turn
import app.agent as agent

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    # --- Auth: real Clerk user ID if configured, else the demo user_id the client sent ---
    user_id = get_current_user_id(authorization, req.user_id)

    # --- Guardrail Layer (PRD 4.8): PII never reaches the agent ---
    guardrail_result = check_pii(req.message)
    if guardrail_result.blocked:
        log_event(
            db,
            "pii_blocked",
            user_id=user_id,
            conversation_id=req.conversation_id,
            payload={"categories": guardrail_result.matched_categories},
        )
        return ChatResponse(
            conversation_id=req.conversation_id or "",
            intent="PII_VIOLATION",
            reply=(
                "For your safety, that message wasn't sent -- it appears to contain sensitive personal "
                "information (like a Social Security number, credit card number, or date of birth). "
                "Please remove that and try again."
            ),
            blocked=True,
        )

    convo = get_or_create_conversation(db, user_id, req.conversation_id)

    # --- Usage & Entitlement (PRD Section 3) -- only meter eligible,
    # subscribed users; ineligible users get agent.run()'s clearer
    # eligibility message instead of a "limit" message. ---
    tier = check_entitlement(db, user_id)
    if tier not in (None, "none"):
        allowed, used, limit = check_and_increment(db, user_id, tier)
        if not allowed:
            return ChatResponse(
                conversation_id=convo.id,
                intent="OUT_OF_SCOPE",
                reply=(
                    f"You've reached today's message limit ({used}/{limit}) for your plan. Limits reset "
                    f"at midnight UTC -- for anything urgent in the meantime, Talk to our AGFinTax Tax Planner."
                ),
            )

    add_turn(db, convo.id, "user", req.message)

    # --- Single agent: deterministic intent -> tool calls -> templated reply ---
    result = agent.run(db, user_id, convo.id, req.message)

    add_turn(db, convo.id, "assistant", result["reply"], intent="AGENT", citations=result["citations"])

    log_event(
        db,
        "chat_turn",
        user_id=user_id,
        conversation_id=convo.id,
        payload={"citations": result["citations"]},
    )

    return ChatResponse(
        conversation_id=convo.id,
        intent="AGENT",
        reply=result["reply"],
        citations=[Citation(**c) for c in result["citations"]],
    )
