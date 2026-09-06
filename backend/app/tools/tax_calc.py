"""
Scenario Agent's tools. All numeric tax logic is deterministic bracket
math against tax_constants -- the LLM is never asked to compute or recall
a number here.
"""
from sqlalchemy.orm import Session

from app.models import TaxConstant


def get_tax_constant(db: Session, tax_year: int, key: str, filing_status: str | None = None):
    q = db.query(TaxConstant).filter(TaxConstant.tax_year == tax_year, TaxConstant.key == key)
    if filing_status:
        q = q.filter(
            (TaxConstant.filing_status == filing_status) | (TaxConstant.filing_status.is_(None))
        )
    row = q.first()
    return row.value if row else None


def _bracket_tax(income: float, brackets: list[dict]) -> float:
    """brackets: [{"upto": 11000, "rate": 0.10}, {"upto": 44725, "rate": 0.12}, ...]
    The final bracket may omit "upto" to mean "and above"."""
    tax = 0.0
    lower = 0.0
    for b in brackets:
        rate = b["rate"]
        upto = b.get("upto")
        if upto is None or income <= upto:
            tax += max(income - lower, 0) * rate
            break
        tax += (upto - lower) * rate
        lower = upto
    return round(tax, 2)


def calculate_tax_scenario(db: Session, tax_year: int, filing_status: str, income: float) -> dict:
    brackets = get_tax_constant(db, tax_year, "federal_income_brackets", filing_status)
    if not brackets:
        raise ValueError(f"No bracket table for {tax_year}/{filing_status}")
    tax = _bracket_tax(income, brackets)
    return {
        "tax_year": tax_year,
        "filing_status": filing_status,
        "income": income,
        "estimated_federal_tax": tax,
        "effective_rate": round(tax / income, 4) if income else 0,
    }
