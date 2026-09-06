from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ScenarioRequest
from app.agents import plan_agent, scenario_agent

router = APIRouter()


@router.get("/tax-plan/{user_id}/{tax_year}")
def get_plan(user_id: str, tax_year: int, db: Session = Depends(get_db)):
    return plan_agent.run(db, user_id, tax_year)


@router.post("/scenarios")
def run_scenario(req: ScenarioRequest, db: Session = Depends(get_db)):
    income = req.changes.get("income", 0)
    return scenario_agent.run(db, req.tax_year, req.filing_status, income)
