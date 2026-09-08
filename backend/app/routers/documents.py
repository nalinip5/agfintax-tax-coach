"""
User-facing document upload.

Pipeline, strictly in this order:
  1. Azure Document Intelligence OCR extracts raw text from the uploaded file.
  2. app.tools.pii_scrub redacts PII from that raw text.
  3. ONLY the scrubbed text is stored (as an unpublished Document/chunks)
     or returned to the caller. The raw extracted text is never persisted,
     never logged, and never passed to the LLM or the agent's tools.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.audit import log_event
from app.db import get_db
from app.tools.document_intelligence import DocumentIntelligenceError, extract_text
from app.tools.knowledge import ingest_document
from app.tools.pii_scrub import scrub_pii

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}


@router.post("/documents/upload")
async def upload_document(
    user_id: str,
    title: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unsupported content type: {file.content_type}")

    raw_bytes = await file.read()

    try:
        raw_text = extract_text(raw_bytes, file.content_type)
    except DocumentIntelligenceError as exc:
        raise HTTPException(502, f"OCR extraction failed: {exc}")
    finally:
        # Belt-and-suspenders: drop the reference to raw bytes as soon as
        # we're done with them; nothing downstream should ever see them.
        del raw_bytes

    scrub_result = scrub_pii(raw_text)
    del raw_text  # raw, unscrubbed text must not survive past this point

    doc = ingest_document(db, title=title, source_domain=None, content=scrub_result.scrubbed_text)

    log_event(
        db,
        "document_uploaded",
        user_id=user_id,
        payload={
            "document_id": doc.id,
            "redacted_categories": scrub_result.redacted_categories,
            "redaction_count": scrub_result.redaction_count,
        },
    )

    return {
        "id": doc.id,
        "title": doc.title,
        "published": doc.published,
        "redacted_categories": scrub_result.redacted_categories,
        "redaction_count": scrub_result.redaction_count,
        "note": "Document ingested with PII redacted prior to storage. Review and publish via the admin tool before it's used in RAG.",
    }
