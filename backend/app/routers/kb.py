from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document, SourceRegistry
from app.schemas import SourceRegistryIn, SourceRegistryOut
from app.tools.knowledge import ingest_document, reindex

router = APIRouter()


# --- Internal documents (admin-uploaded knowledge) ---

@router.post("/kb/documents")
def upload_document(title: str, source_domain: str | None, content: str, db: Session = Depends(get_db)):
    doc = ingest_document(db, title, source_domain, content)
    return {"id": doc.id, "title": doc.title, "published": doc.published}


@router.post("/kb/documents/{document_id}/publish")
def publish_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.published = True
    db.commit()
    return {"id": doc.id, "published": True}


@router.post("/kb/documents/{document_id}/unpublish")
def unpublish_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    doc.published = False
    db.commit()
    return {"id": doc.id, "published": False}


@router.post("/kb/reindex")
def kb_reindex():
    return reindex()


# --- source_registry: DB-driven official-source registry ---
# Adding a new government source is a POST here (a DB insert) -- no
# code deploy required, matching the architecture's "zero code changes".

@router.get("/kb/sources", response_model=list[SourceRegistryOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(SourceRegistry).all()


@router.post("/kb/sources", response_model=SourceRegistryOut)
def create_source(body: SourceRegistryIn, db: Session = Depends(get_db)):
    row = SourceRegistry(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/kb/sources/{source_id}", response_model=SourceRegistryOut)
def update_source(source_id: str, body: SourceRegistryIn, db: Session = Depends(get_db)):
    row = db.query(SourceRegistry).filter(SourceRegistry.id == source_id).first()
    if not row:
        raise HTTPException(404, "Source not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/kb/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    row = db.query(SourceRegistry).filter(SourceRegistry.id == source_id).first()
    if not row:
        raise HTTPException(404, "Source not found")
    db.delete(row)
    db.commit()
    return {"deleted": source_id}
