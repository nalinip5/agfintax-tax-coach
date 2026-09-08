"""
RAG Agent's tools.

search_internal_knowledge() -- hybrid vector + full-text search over
admin-curated, published documents.

search_official_sources() -- looks up which government domains are
enabled and in-scope for this query via the source_registry table, uses
Tavily to discover the specific matching page(s) on those domains, then
fetches and extracts the REAL page content (see web_extract.py) rather
than relying on a short search-engine snippet -- the same "find it, then
extract the actual content" pattern used for uploaded documents via
Azure Document Intelligence. Adding a new government source is a DB
insert; this function never changes when new sources are added.
"""
from urllib.parse import urlparse

import httpx
from sqlalchemy import or_ as sa_or
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Document, DocumentChunk, SourceRegistry
from app.tools.web_extract import extract_page_content

# PRD Section 5: Tax Coach may retrieve from ONLY these domains, under any
# circumstance. This is enforced here in code -- not just via the
# source_registry table -- so a future erroneous DB row can never expand
# retrieval beyond this approved list. To add a source, it must first be
# added to this constant (a deploy), then enabled in source_registry (a
# DB insert) -- both steps required, by design, for this specific list.
APPROVED_SOURCE_DOMAINS = frozenset({
    "irs.gov",
    "treasury.gov",
    "ssa.gov",
    "cms.gov",
    "dol.gov",
    "pbgc.gov",
    "sec.gov",
})


def search_internal_knowledge(db: Session, query: str, limit: int = 5) -> list[dict]:
    """Keyword OR-match across query terms, ranked by number of terms hit.
    Suitable for SQLite/dev. On Postgres, swap for a pgvector similarity
    search / tsvector full-text query -- callers don't need to change."""
    terms = [t for t in query.split() if len(t) > 2]
    if not terms:
        return []

    rows = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.published.is_(True))
        .filter(sa_or(*[DocumentChunk.content.ilike(f"%{t}%") for t in terms]))
        .all()
    )

    def score(chunk: DocumentChunk) -> int:
        text = chunk.content.lower()
        return sum(1 for t in terms if t.lower() in text)

    ranked = sorted(rows, key=score, reverse=True)[:limit]
    return [
        {"document_id": r.document_id, "content": r.content, "source_domain": r.document.source_domain}
        for r in ranked
    ]


def _matching_registry_rows(db: Session, scope_tags: list[str], tier: str) -> list[SourceRegistry]:
    rows = db.query(SourceRegistry).filter(SourceRegistry.enabled.is_(True)).all()

    def matches(row: SourceRegistry) -> bool:
        if row.domain not in APPROVED_SOURCE_DOMAINS:
            return False  # hard policy floor -- see APPROVED_SOURCE_DOMAINS above
        tags_ok = not scope_tags or any(tag in (row.scope_tags or []) for tag in scope_tags)
        tier_ok = tier in (row.tier or [])
        return tags_ok and tier_ok

    return [r for r in rows if matches(r)]


def _tavily_discover(query: str, include_domains: list[str], max_results: int = 4) -> list[dict]:
    """Uses Tavily purely for discovery -- which specific page on which
    domain is relevant -- not as the content source itself."""
    settings = get_settings()
    if not settings.tavily_api_key or not include_domains:
        return []
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "include_domains": include_domains,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    results = []
    for r in data.get("results", []):
        domain = urlparse(r.get("url", "")).netloc.removeprefix("www.")
        results.append({"domain": domain, "title": r.get("title", ""), "url": r.get("url", ""), "tavily_snippet": r.get("content", "")[:500]})
    return results


def search_official_sources(db: Session, scope_tags: list[str], tier: str, query: str | None = None) -> list[dict]:
    """Return real extracted page content from official sources, scoped
    to enabled source_registry domains matching scope/tier.

    Pipeline: source_registry decides WHICH domains are in scope (data-
    driven, per-tier) -> Tavily discovers the specific matching page(s) on
    those domains -> web_extract fetches and parses the ACTUAL page
    content. If extraction fails for a given URL, that result falls back
    to Tavily's own snippet rather than being dropped. If Tavily itself
    isn't configured or returns nothing, falls back to bare registry
    metadata so callers always get a usable, non-empty-shaped list.

    api_method on a registry row (tavily_search / direct_fetch / irs_api)
    is informational for now -- all currently route through the same
    discover-then-extract pipeline, since Tavily can discover pages on
    any public domain regardless of that label. A dedicated IRS API
    integration can later special-case api_method == "irs_api" here
    without changing this function's signature or callers.
    """
    rows = _matching_registry_rows(db, scope_tags, tier)
    domains = [r.domain for r in rows]

    if query and domains:
        discovered = _tavily_discover(query, domains)
        if discovered:
            results = []
            for d in discovered:
                extracted = extract_page_content(d["url"])
                results.append(
                    {
                        "domain": d["domain"],
                        "title": d["title"],
                        "url": d["url"],
                        "content": extracted if extracted else d["tavily_snippet"],
                        "content_source": "extracted" if extracted else "tavily_snippet",
                    }
                )
            # PRD Section 6 (Audit): every official-source query must be
            # logged with the query and the source URL(s) returned.
            from app.audit import log_event
            log_event(db, "official_source_query", payload={"query": query, "urls": [r["url"] for r in results]})
            return results

    # Fallback: registry metadata only, no live fetch (Tavily not
    # configured, no query given, or discovery returned nothing).
    return [
        {"domain": r.domain, "title": r.description, "url": f"https://www.{r.domain}", "content": r.description, "content_source": "registry_metadata"}
        for r in rows
    ]


def ingest_document(db: Session, title: str, source_domain: str | None, content: str) -> Document:
    doc = Document(title=title, source_domain=source_domain, published=False)
    db.add(doc)
    db.flush()

    # naive fixed-size chunking; swap for a real splitter + embedding model
    chunk_size = 800
    for i in range(0, len(content), chunk_size):
        db.add(DocumentChunk(document_id=doc.id, content=content[i : i + chunk_size]))

    db.commit()
    db.refresh(doc)
    return doc


def reindex() -> dict:
    """Placeholder hook for a background re-embedding job."""
    return {"status": "reindex_scheduled"}

