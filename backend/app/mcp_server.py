"""
MCP server exposing AGFinTax's tools -- internal RAG, external RAG
(live official-source discovery + real page-content extraction),
deterministic tax math, plan lookup, and professional referrals -- via
the actual Model Context Protocol (not just an internal schema).

Any MCP-compatible client can connect to this: the app's own agent
(app/mcp_client.py), Claude Desktop, or any other MCP host. Tools are
discovered dynamically via the protocol's list_tools, not hardcoded on
the client side.

Run standalone for inspection:
    python -m app.mcp_server
"""
import json

from mcp.server.fastmcp import FastMCP

from app.db import SessionLocal
from app.tools.knowledge import (
    search_internal_knowledge as _search_internal_knowledge,
    search_official_sources as _search_official_sources,
    ingest_document as _ingest_document,
)
from app.tools.tax_calc import (
    calculate_tax_scenario as _calculate_tax_scenario,
    get_tax_constant as _get_tax_constant,
)
from app.tools.tax_plan import get_tax_plan as _get_tax_plan, check_entitlement as _check_entitlement
from app.tools.conversation import create_professional_referral as _create_professional_referral
from app.tools.document_intelligence import extract_text as _extract_text, DocumentIntelligenceError
from app.tools.pii_scrub import scrub_pii as _scrub_pii

mcp = FastMCP("agfintax-tools")


@mcp.tool()
def search_internal_knowledge(query: str) -> str:
    """Internal RAG: keyword search over admin-curated, published internal
    tax documents (e.g. the OBBBA summary). Returns a JSON-encoded list."""
    db = SessionLocal()
    try:
        return json.dumps(_search_internal_knowledge(db, query))
    finally:
        db.close()


@mcp.tool()
def search_official_sources(query: str, user_id: str, scope_tags: list[str] = []) -> str:
    """External RAG: discovers the matching page on enabled government
    domains (source_registry, filtered by scope/tier) via live Tavily
    search, then fetches and extracts the REAL page content -- not just a
    search snippet. Returns a JSON-encoded list."""
    db = SessionLocal()
    try:
        tier = _check_entitlement(db, user_id)
        return json.dumps(_search_official_sources(db, scope_tags, tier, query=query))
    finally:
        db.close()


@mcp.tool()
def get_tax_plan(user_id: str, tax_year: int) -> str:
    """Look up the user's saved tax plan and strategies for a given year.
    Returns a JSON-encoded dict."""
    db = SessionLocal()
    try:
        plan = _get_tax_plan(db, user_id, tax_year)
        if not plan:
            return json.dumps({"found": False})
        return json.dumps({"found": True, "filing_status": plan.filing_status, "strategies": [s.title for s in plan.strategies]})
    finally:
        db.close()


@mcp.tool()
def calculate_tax_scenario(tax_year: int, filing_status: str, income: float) -> str:
    """Deterministic federal tax bracket calculation -- never estimated by
    an LLM. Falls back to the most recent published bracket year if the
    exact requested year isn't available yet. Returns a JSON-encoded dict."""
    db = SessionLocal()
    try:
        try:
            return json.dumps(_calculate_tax_scenario(db, tax_year, filing_status, income))
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
    finally:
        db.close()


@mcp.tool()
def get_tax_constant(tax_year: int, key: str, filing_status: str | None = None) -> str:
    """Look up a specific deterministic tax constant (contribution limit,
    bracket table, etc.) for a tax year. Returns a JSON-encoded dict."""
    db = SessionLocal()
    try:
        value, actual_year = _get_tax_constant(db, tax_year, key, filing_status)
        return json.dumps({"value": value, "actual_year": actual_year})
    finally:
        db.close()


@mcp.tool()
def create_professional_referral(user_id: str, conversation_id: str, reason: str) -> str:
    """Flag this conversation for a licensed-professional referral (life
    events, judgment calls the agent shouldn't answer definitively).
    Returns a JSON-encoded dict."""
    db = SessionLocal()
    try:
        _create_professional_referral(db, user_id, conversation_id, reason)
        return json.dumps({"referred": True})
    finally:
        db.close()


@mcp.tool()
def upload_and_extract_document(title: str, file_base64: str, content_type: str) -> str:
    """Document Intelligence tool: OCR-extracts text from an uploaded file
    (base64-encoded) via Azure Document Intelligence, redacts PII from the
    RAW extracted text BEFORE anything else happens, and only then ingests
    the scrubbed text as an internal (unpublished) document.

    Security guarantee: the raw, unscrubbed OCR output never leaves this
    function -- it is not returned, not logged, and not passed to any
    other tool or caller. Only the scrubbed text and redaction summary
    are ever surfaced. Returns a JSON-encoded dict."""
    import base64

    db = SessionLocal()
    try:
        raw_bytes = base64.b64decode(file_base64)
        try:
            raw_text = _extract_text(raw_bytes, content_type)
        except DocumentIntelligenceError as exc:
            return json.dumps({"error": f"OCR extraction failed: {exc}"})
        finally:
            del raw_bytes

        scrub_result = _scrub_pii(raw_text)
        del raw_text  # raw, unscrubbed text must not survive past this point

        doc = _ingest_document(db, title=title, source_domain=None, content=scrub_result.scrubbed_text)
        return json.dumps(
            {
                "id": doc.id,
                "title": doc.title,
                "published": doc.published,
                "redacted_categories": scrub_result.redacted_categories,
                "redaction_count": scrub_result.redaction_count,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
