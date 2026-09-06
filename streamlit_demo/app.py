"""
AGFinTax — Streamlit demo.

Deploy this file on Streamlit Community Cloud (share.streamlit.io) to get
a free, public URL for client demos. It calls the exact same backend
pipeline as the FastAPI app (app.guardrail -> app.supervisor ->
app.agents.* -> app.tools.*) directly in-process -- no separate server,
so behavior matches the "real" app exactly, just packaged for one-click
hosting.

This file lives in its own folder with its own requirements.txt so it
never shares a dependency file with the FastAPI backend (streamlit and
fastapi pin incompatible starlette versions if installed together).

Streamlit Cloud setup:
  1. Push this repo to GitHub.
  2. share.streamlit.io -> New app -> pick the repo -> main file path:
     streamlit_demo/app.py
  3. In "Advanced settings -> Secrets", add (TOML format):
       ANTHROPIC_API_KEY = "sk-ant-..."
       LLM_PROVIDER = "anthropic"
       LLM_MODEL = "claude-sonnet-4-6"
  4. Deploy. Note: the demo's SQLite database resets on redeploy/restart --
     fine for a client demo, not meant for persistent production data.
"""
import os
import sys
from pathlib import Path

import streamlit as st

# --- Wire Streamlit secrets into env vars BEFORE importing the backend,
# since app.config reads os.environ at first import and caches it. ---
for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "DATABASE_URL"]:
    if key in st.secrets:
        os.environ[key] = str(st.secrets[key])

# --- Make the FastAPI backend's `app` package importable from here. ---
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal  # noqa: E402
from app.guardrail import check_pii  # noqa: E402
from app.supervisor import route, Intent  # noqa: E402
from app.tools.tax_plan import check_entitlement  # noqa: E402
from app.tools.usage import check_and_increment  # noqa: E402
from app.tools.conversation import get_or_create_conversation, add_turn  # noqa: E402
from app.agents import plan_agent, rag_agent, scenario_agent, life_event_agent, composer  # noqa: E402
from app.models import SourceRegistry  # noqa: E402
import app.seed  # noqa: E402,F401 -- idempotent: creates tables + demo data on first run

USER_ID = "demo-user"

st.set_page_config(page_title="AGFinTax — Agentic Tax Coach", page_icon="🧾", layout="wide")


def run_pipeline(db, message: str) -> dict:
    """Mirrors backend/app/routers/chat.py's POST /api/chat exactly."""
    guardrail_result = check_pii(message)
    if guardrail_result.blocked:
        return {
            "intent": Intent.PII_VIOLATION.value,
            "reply": (
                "For your safety, I can't process messages containing sensitive personal "
                "information like SSNs, account numbers, or passwords. Please remove that "
                "and try again."
            ),
            "citations": [],
        }

    convo = get_or_create_conversation(db, USER_ID, st.session_state.get("conversation_id"))
    st.session_state["conversation_id"] = convo.id

    tier = check_entitlement(db, USER_ID)
    allowed, used, limit = check_and_increment(db, USER_ID, tier)
    if not allowed:
        return {
            "intent": Intent.OUT_OF_SCOPE.value,
            "reply": f"You've hit today's message limit ({used}/{limit}) for the {tier} plan.",
            "citations": [],
        }

    add_turn(db, convo.id, "user", message)
    intent = route(message)

    import datetime
    context: dict = {}
    if intent == Intent.PLAN_QUESTION:
        context["plan"] = plan_agent.run(db, USER_ID, datetime.date.today().year)
    elif intent == Intent.WHAT_IF:
        context["scenario"] = scenario_agent.run(db, datetime.date.today().year, "single", 90000)
        context["rag"] = rag_agent.run(db, USER_ID, message)
    elif intent == Intent.LIFE_EVENT:
        context["life_event"] = life_event_agent.run(db, USER_ID, convo.id, message)
        context["rag"] = rag_agent.run(db, USER_ID, message)
    elif intent == Intent.OUT_OF_SCOPE:
        reply = "That's outside what I can help with as a tax coach."
        add_turn(db, convo.id, "assistant", reply, intent=intent.value)
        return {"intent": intent.value, "reply": reply, "citations": []}
    else:
        context["rag"] = rag_agent.run(db, USER_ID, message)

    result = composer.run(intent.value, message, context)
    add_turn(db, convo.id, "assistant", result["reply"], intent=intent.value, citations=result["citations"])
    return {"intent": intent.value, "reply": result["reply"], "citations": result["citations"]}


def chat_tab():
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "I'm your tax coach. Ask about your plan, a tax rule, or try a what-if scenario."}
        ]

    for m in st.session_state["messages"]:
        with st.chat_message(m["role"]):
            if m.get("intent"):
                st.caption(m["intent"])
            st.write(m["content"])
            for c in m.get("citations", []):
                st.markdown(f"[{c['label']}]({c['url']})")

    if prompt := st.chat_input("Ask about your taxes…"):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        db = SessionLocal()
        try:
            result = run_pipeline(db, prompt)
        finally:
            db.close()

        st.session_state["messages"].append(
            {"role": "assistant", "content": result["reply"], "intent": result["intent"], "citations": result["citations"]}
        )
        with st.chat_message("assistant"):
            st.caption(result["intent"])
            st.write(result["reply"])
            for c in result["citations"]:
                st.markdown(f"[{c['label']}]({c['url']})")


def admin_tab():
    st.caption("DB-driven official-source registry. Adding a row here is the only step — no deploy.")

    db = SessionLocal()
    try:
        sources = db.query(SourceRegistry).all()
        rows = [
            {
                "domain": s.domain,
                "description": s.description,
                "scope_tags": ", ".join(s.scope_tags or []),
                "api_method": s.api_method,
                "tier": ", ".join(s.tier or []),
                "enabled": s.enabled,
            }
            for s in sources
        ]
        st.dataframe(rows, use_container_width=True)

        with st.form("add_source", clear_on_submit=True):
            st.write("Add a new source")
            col1, col2 = st.columns(2)
            domain = col1.text_input("domain (e.g. hud.gov)")
            description = col2.text_input("description")
            scope_tags = col1.text_input("scope_tags (comma separated)")
            api_method = col2.selectbox("api_method", ["tavily_search", "direct_fetch", "irs_api"])
            submitted = st.form_submit_button("Add source")
            if submitted and domain:
                db.add(
                    SourceRegistry(
                        domain=domain,
                        description=description or "",
                        scope_tags=[t.strip() for t in scope_tags.split(",") if t.strip()],
                        api_method=api_method,
                        enabled=True,
                        tier=["basic", "plus", "pro"],
                    )
                )
                db.commit()
                st.success(f"Added {domain} — no code change, no deploy.")
                st.rerun()
    finally:
        db.close()


st.title("🧾 AGFinTax — Agentic Tax Coach")
tab1, tab2 = st.tabs(["Chat", "Admin"])
with tab1:
    chat_tab()
with tab2:
    admin_tab()
