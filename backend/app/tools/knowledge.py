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
import re

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
    "congress.gov",
})


_STOPWORDS = {
    "the", "and", "for", "that", "this", "what", "are", "does", "with", "from", "your",
    "you", "have", "will", "can", "how", "who", "why", "when", "which", "about", "into",
    "strategy", "strategies", "tell", "know", "want", "need", "get", "any", "some",
}


# Lightweight semantic matching -- NOT true embedding-based semantic
# search (deliberately avoided: a local embedding model is a heavy
# dependency, and we already hit a real reliability failure once from
# adding weight to this app's request path -- see app/mcp_bridge.py's
# history). This is simple term normalization plus a small curated
# synonym set for common tax vocabulary, so a query using a different
# but equivalent word/form than the source document can still match.
_SYNONYMS = {
    "sep-ira": ["sep", "sep ira", "simplified employee pension"],
    "hsa": ["health savings account"],
    "deduction": ["deduct", "deductible", "deducting"],
    "contribution": ["contribute", "contributing", "contributed"],
    "withholding": ["withhold", "withheld"],
    "credit": ["credits"],
    "ira": ["individual retirement"],
}


def _expand_term(term: str) -> list[str]:
    """A term plus its simple stem (trailing s/es/ing/ed stripped, if the
    remaining stem is still meaningful) plus any curated synonyms --
    every variant a query term could reasonably match against."""
    lowered = term.lower()
    variants = {lowered}
    for suffix in ("ing", "ed", "s"):
        if lowered.endswith(suffix) and len(lowered) - len(suffix) >= 3:
            variants.add(lowered[: -len(suffix)])
            break
    for key, synonyms in _SYNONYMS.items():
        if lowered == key or lowered in synonyms:
            variants.add(key)
            variants.update(synonyms)
    return list(variants)


def search_internal_knowledge(db: Session, query: str, limit: int = 5) -> list[dict]:
    """Keyword OR-match across query terms (plus simple stemming and a
    small curated tax-vocabulary synonym set -- see _expand_term), ranked
    by number of terms hit. Suitable for SQLite/dev. On Postgres, swap
    for a pgvector similarity search / tsvector full-text query --
    callers don't need to change.

    Requires a meaningful fraction of SIGNIFICANT (non-stopword) query
    terms to actually match -- a document must not be presented as
    relevant just because it happens to share a few common words with the
    question. Every fact-bearing reply must trace to genuinely relevant
    source content, not a coincidental keyword collision.
    """
    all_terms = [t.strip(".,?!:;\"'()") for t in query.split()]
    all_terms = [t for t in all_terms if len(t) > 2]
    significant_terms = [t for t in all_terms if t.lower() not in _STOPWORDS]
    if not significant_terms:
        return []

    term_variants = {t: _expand_term(t) for t in significant_terms}
    all_variants = [v for variants in term_variants.values() for v in variants]

    rows = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.published.is_(True))
        .filter(sa_or(*[DocumentChunk.content.ilike(f"%{v}%") for v in all_variants]))
        .all()
    )

    def score(chunk: DocumentChunk) -> float:
        # Content match is the base score; a title match on the same term
        # adds a bonus -- a document specifically TITLED around a term is
        # more likely the right match than one that merely mentions it in
        # passing. Confirmed necessary in practice: "home office
        # deduction rules" tied 0.75/0.75 between the correct "Home
        # Office Deduction" document and an unrelated "Augusta Rule" one
        # that happened to also mention "rules," "home," and "deduction"
        # -- with no tie-breaker, insertion order picked the wrong one.
        text = chunk.content.lower()
        title = (chunk.document.title or "").lower()
        content_matches = sum(1 for t, variants in term_variants.items() if any(v in text for v in variants))
        title_matches = sum(1 for t, variants in term_variants.items() if any(v in title for v in variants))
        return content_matches / len(significant_terms) + 0.1 * title_matches

    # Require at least half of the significant query terms to genuinely
    # appear in the chunk -- filters out documents that only coincidentally
    # share one unrelated word with the question.
    scored = [(c, score(c)) for c in rows]
    relevant = [(c, s) for c, s in scored if s >= 0.5]
    ranked = sorted(relevant, key=lambda cs: cs[1], reverse=True)[:limit]
    ranked = [c for c, _ in ranked]
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


def _authority_tier(title: str, url: str) -> int:
    """Real authority scoring (deterministic, no ML/embedding dependency --
    a heavy local embedding model would risk the same resource-constraint
    failure that per-message MCP subprocess spawning caused on Render's
    free tier). Ranks 1 (highest, primary regulatory text) to 3 (lowest,
    press releases and historical notices) so a page like "IRS Repeats
    Warning about Phone Scams" -- a real .gov page, but a press release,
    not guidance -- is deprioritized under a genuine Publication or
    topic-overview page on the same domain."""
    text = f"{title} {url}".lower()
    if any(t in text for t in ["publication ", "/publications/", "form ", "instructions for", "revenue ruling", "revenue procedure", "treasury regulation", "26 cfr", "26 u.s.c"]):
        return 1
    if "/newsroom/" in text or "historical content" in text or "press release" in text or "news release" in text:
        return 3
    return 2


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
        # Hard policy floor, enforced here regardless of whether Tavily's
        # own include_domains restriction actually held -- an external
        # search API is not a trusted enforcement boundary by itself.
        # Confirmed necessary in practice: a real query returned adp.com
        # and en.wikipedia.org despite include_domains being set to only
        # approved government domains.
        if domain not in APPROVED_SOURCE_DOMAINS:
            continue
        title = r.get("title", "")
        url = r.get("url", "")
        results.append({"domain": domain, "title": title, "url": url, "tavily_snippet": r.get("content", "")[:500], "authority_tier": _authority_tier(title, url)})
    # Exclude tier-3 (press release / historical notice) results entirely,
    # not just deprioritize them. Confirmed necessary in practice: a
    # newsroom press release ("IRS reminds taxpayers of the home office
    # deduction rules during Small Business Week") was the ONLY candidate
    # returned, so sorting alone couldn't help -- it still got presented
    # as the answer, and its actual extracted content turned out to be a
    # navigation menu and language-switcher links, not substantive
    # guidance. A stale press release is not useful guidance regardless
    # of topical relevance -- better to return nothing here (triggering
    # the honest "couldn't retrieve guidance" fallback) than to ever
    # present one as if it answers the question.
    results = [r for r in results if r["authority_tier"] < 3]
    results.sort(key=lambda r: r["authority_tier"])  # tier 1 (highest authority) first
    return results


# Shared with search_internal_knowledge's relevance logic -- external
# results need the same floor, or Tavily can hand back a technically-real
# but totally irrelevant page (e.g. a query about a specific deduction
# returning an unrelated IRS phone-scam warning) and we'd present it as
# if it answered the question. A real result is worse than an honest
# "couldn't retrieve" when it's this unrelated -- it looks authoritative
# but isn't.
_PROPER_NOUN_PHRASE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


def _is_relevant(query: str, title: str, content: str) -> bool:
    """A result counts as relevant if EITHER: the title itself contains a
    real query term (titles are a strong, concise relevance signal even
    when extracted body content is sparse), OR at least a third of the
    query's significant terms appear across title+content combined. Two
    paths rather than one fixed ratio, because a compound question
    ("IRMAA thresholds AND FICA wage base") can be genuinely, correctly
    answered by a source covering only part of it -- that's partial
    coverage, not a bad match. This only needs to be strict enough to
    reject a completely unrelated page (e.g. a phone-scam warning
    returned for an "Augusta Rule" query), which is the actual failure
    mode it exists to catch.

    EXCEPTION for named-concept queries (e.g. "Augusta Rule"): a single
    shared word is not enough. Confirmed necessary in practice -- a
    congress.gov page about a representative named Hatcher passed the
    single-term-title check purely because his district/bio happened to
    mention "Augusta" (a place name), with zero actual connection to the
    tax provision informally called the Augusta Rule. When the query
    names a specific multi-word phrase, only the phrase itself appearing
    together counts -- individual constituent words are too likely to
    coincidentally appear elsewhere (place names, person names) to be a
    reliable relevance signal on their own.
    """
    terms = [t for t in query.split() if len(t) > 2 and t.lower() not in _STOPWORDS]
    if not terms:
        return True  # nothing meaningful to check against; don't over-reject

    haystack = f"{title} {content}".lower()

    phrase_match = _PROPER_NOUN_PHRASE.search(query)
    if phrase_match:
        return phrase_match.group(1).lower() in haystack

    title_lower = title.lower()
    if any(t.lower() in title_lower for t in terms):
        return True
    matched = sum(1 for t in terms if t.lower() in haystack)
    return matched / len(terms) >= 1 / 3


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
                content = extracted if extracted else d["tavily_snippet"]
                if not _is_relevant(query, d["title"], content):
                    continue  # discard -- real content, but not actually about the question asked
                results.append(
                    {
                        "domain": d["domain"],
                        "title": d["title"],
                        "url": d["url"],
                        "content": content,
                        "content_source": "extracted" if extracted else "tavily_snippet",
                        "authority_tier": d["authority_tier"],
                    }
                )
            if results:
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

