from sqlalchemy.orm import Session

from app.tools.tax_calc import calculate_tax_scenario


def run(db: Session, tax_year: int, filing_status: str, income: float) -> dict:
    try:
        return {"ok": True, "result": calculate_tax_scenario(db, tax_year, filing_status, income)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
