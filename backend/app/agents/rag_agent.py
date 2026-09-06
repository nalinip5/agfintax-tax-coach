from sqlalchemy.orm import Session

from app.tools.knowledge import search_internal_knowledge, search_official_sources
from app.tools.tax_plan import check_entitlement


_SCOPE_KEYWORDS = {
    "retirement": ["401k", "ira", "retirement", "roth"],
    "business": ["llc", "self-employed", "schedule c", "business"],
    "real_estate": ["mortgage", "rental", "home sale", "real estate"],
}


def _infer_scope_tags(message: str) -> list[str]:
    lowered = message.lower()
    return [tag for tag, kws in _SCOPE_KEYWORDS.items() if any(kw in lowered for kw in kws)]


def run(db: Session, user_id: str, message: str) -> dict:
    tier = check_entitlement(db, user_id)
    internal_hits = search_internal_knowledge(db, message)
    scope_tags = _infer_scope_tags(message)
    official_sources = search_official_sources(db, scope_tags, tier)
    return {
        "internal_hits": internal_hits,
        "official_sources": official_sources,
        "scope_tags": scope_tags,
    }
