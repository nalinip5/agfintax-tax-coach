"""
RAG Agent's tools.

search_internal_knowledge() -- hybrid vector + full-text search over
admin-curated, published documents.

search_official_sources() -- looks up which government domains are
enabled and in-scope for this query by reading the source_registry table.
Adding a new government source is a DB insert; this function never
changes when new sources are added.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, SourceRegistry


def search_internal_knowledge(db: Session, query: str, limit: int = 5) -> list[dict]:
    """Simple full-text fallback (LIKE match) suitable for SQLite/dev.
    On Postgres, swap the filter for a pgvector similarity search /
    tsvector full-text query -- callers don't need to change."""
    like = f"%{query}%"
    rows = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.published.is_(True))
        .filter(DocumentChunk.content.ilike(like))
        .limit(limit)
        .all()
    )
    return [
        {"document_id": r.document_id, "content": r.content, "source_domain": r.document.source_domain}
        for r in rows
    ]


def search_official_sources(db: Session, scope_tags: list[str], tier: str) -> list[dict]:
    """Return enabled source_registry rows matching the requested scope
    and the caller's subscription tier. This is the entire "which
    government sites can I query" decision -- purely data-driven."""
    query = db.query(SourceRegistry).filter(SourceRegistry.enabled.is_(True))
    rows = query.all()

    def matches(row: SourceRegistry) -> bool:
        tags_ok = not scope_tags or any(tag in (row.scope_tags or []) for tag in scope_tags)
        tier_ok = tier in (row.tier or [])
        return tags_ok and tier_ok

    return [
        {
            "domain": r.domain,
            "description": r.description,
            "api_method": r.api_method,
            "scope_tags": r.scope_tags,
        }
        for r in rows
        if matches(r)
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
