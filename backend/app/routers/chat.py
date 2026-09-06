from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import log_event
from app.db import get_db
from app.guardrail import check_pii
from app.schemas import ChatRequest, ChatResponse, Citation
from app.supervisor import route, Intent
from app.tools.tax_plan import check_entitlement
from app.tools.usage import check_and_increment
from app.tools.conversation import (
    get_or_create_conversation,
    add_turn,
)
from app.agents import plan_agent, rag_agent, scenario_agent, life_event_agent, composer

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # --- Guardrail Layer: PII never reaches the supervisor or any LLM ---
    guardrail_result = check_pii(req.message)
    if guardrail_result.blocked:
        log_event(
            db,
            "pii_blocked",
            user_id=req.user_id,
            conversation_id=req.conversation_id,
            payload={"categories": guardrail_result.matched_categories},
        )
        return ChatResponse(
            conversation_id=req.conversation_id or "",
            intent=Intent.PII_VIOLATION.value,
            reply=(
                "For your safety, I can't process messages containing sensitive personal "
                "information like SSNs, account numbers, or passwords. Please remove that "
                "and try again."
            ),
            blocked=True,
        )

    convo = get_or_create_conversation(db, req.user_id, req.conversation_id)

    # --- Usage & Entitlement Service ---
    tier = check_entitlement(db, req.user_id)
    allowed, used, limit = check_and_increment(db, req.user_id, tier)
    if not allowed:
        return ChatResponse(
            conversation_id=convo.id,
            intent=Intent.OUT_OF_SCOPE.value,
            reply=f"You've hit today's message limit ({used}/{limit}) for your plan. Try again tomorrow.",
        )

    add_turn(db, convo.id, "user", req.message)

    # --- Orchestration: Supervisor routes intent (deterministic) ---
    intent = route(req.message)

    # --- Agent Layer + Tools & Services ---
    context: dict = {}
    if intent == Intent.PLAN_QUESTION:
        context["plan"] = plan_agent.run(db, req.user_id, date.today().year)
    elif intent == Intent.WHAT_IF:
        context["scenario"] = scenario_agent.run(db, date.today().year, "single", 90000)
        context["rag"] = rag_agent.run(db, req.user_id, req.message)
    elif intent == Intent.LIFE_EVENT:
        context["life_event"] = life_event_agent.run(db, req.user_id, convo.id, req.message)
        context["rag"] = rag_agent.run(db, req.user_id, req.message)
    elif intent == Intent.OUT_OF_SCOPE:
        add_turn(db, convo.id, "assistant", "That's outside what I can help with as a tax coach.", intent=intent.value)
        return ChatResponse(conversation_id=convo.id, intent=intent.value, reply="That's outside what I can help with as a tax coach.")
    else:
        context["rag"] = rag_agent.run(db, req.user_id, req.message)

    # --- Composer: LLM (ENV-configured provider/model) + deterministic fallback ---
    result = composer.run(intent.value, req.message, context)

    add_turn(
        db, convo.id, "assistant", result["reply"], intent=intent.value, citations=result["citations"]
    )

    log_event(
        db,
        "chat_turn",
        user_id=req.user_id,
        conversation_id=convo.id,
        payload={"intent": intent.value, "verification": result["verification"]},
    )

    return ChatResponse(
        conversation_id=convo.id,
        intent=intent.value,
        reply=result["reply"],
        citations=[Citation(**c) for c in result["citations"]],
    )
