"""
Web page content extraction for official government sources.

This is the web analog of app.tools.document_intelligence: given a URL
(found via Tavily search), fetch the actual page and extract clean,
readable text -- not just a search-engine snippet. The agent's
search_official_sources tool uses this so grounding is based on the real
page content, the same way an uploaded document's real OCR'd text (not a
guess) grounds a document-based answer.
"""
import re

import httpx

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AGFinTaxBot/1.0; +https://agfintax.example/bot)"}
_MAX_CHARS = 4000


def extract_page_content(url: str, timeout: float = 8.0) -> str | None:
    """Fetches `url` and returns cleaned, extracted text, or None if the
    fetch/parse fails for any reason -- callers should fall back to
    whatever snippet they already have rather than error out."""
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        return None

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
    except Exception:
        # Fallback if bs4 isn't available or parsing fails: crude tag strip.
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)

    # Collapse excess whitespace left behind by stripped tags.
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned[:_MAX_CHARS] if cleaned else None
