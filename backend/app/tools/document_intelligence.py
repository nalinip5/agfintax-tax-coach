"""
Document extraction via Azure AI Document Intelligence (prebuilt-read OCR).

This is the ONLY place raw, un-scrubbed document text exists. The caller
(see app/routers/documents.py) must run the result through
app.tools.pii_scrub.scrub_pii() before storing, ingesting for RAG, or
passing anything to an LLM.
"""
import time

import httpx

from app.config import get_settings


class DocumentIntelligenceError(RuntimeError):
    pass


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Submits a document to Azure Document Intelligence's prebuilt-read
    model and polls for the OCR result. Raises DocumentIntelligenceError
    if not configured or the call fails -- callers should surface a clear
    error rather than silently skipping extraction."""
    settings = get_settings()
    if not settings.azure_di_endpoint or not settings.azure_di_key:
        raise DocumentIntelligenceError("Azure Document Intelligence is not configured (AZURE_DI_ENDPOINT / AZURE_DI_KEY)")

    submit_url = f"{settings.azure_di_endpoint.rstrip('/')}/documentintelligence/documentModels/prebuilt-read:analyze"
    headers = {"Ocp-Apim-Subscription-Key": settings.azure_di_key, "Content-Type": content_type}
    params = {"api-version": "2024-11-30"}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(submit_url, headers=headers, params=params, content=file_bytes)
        if resp.status_code != 202:
            raise DocumentIntelligenceError(f"Azure DI submit failed: {resp.status_code} {resp.text[:300]}")

        operation_url = resp.headers.get("Operation-Location")
        if not operation_url:
            raise DocumentIntelligenceError("Azure DI did not return an Operation-Location header")

        # Poll for completion (prebuilt-read is typically fast for single documents).
        for _ in range(20):
            time.sleep(1.0)
            poll = client.get(operation_url, headers={"Ocp-Apim-Subscription-Key": settings.azure_di_key})
            poll.raise_for_status()
            data = poll.json()
            status = data.get("status")
            if status == "succeeded":
                return data.get("analyzeResult", {}).get("content", "")
            if status == "failed":
                raise DocumentIntelligenceError(f"Azure DI analysis failed: {data}")

    raise DocumentIntelligenceError("Azure DI analysis timed out waiting for a result")
