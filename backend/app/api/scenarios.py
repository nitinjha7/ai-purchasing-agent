from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import scenario_runner
from app.api.deps import get_db
from app.domain.models import AgentRunOut

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class RecommendationReviewRequest(BaseModel):
    sku: str
    recommended_qty: int


class SupplierShortfallRequest(BaseModel):
    po_id: int
    fulfilled_qty: int


@router.post("/recommendation-review", response_model=AgentRunOut)
def recommendation_review(body: RecommendationReviewRequest, db: Session = Depends(get_db)):
    agent_run = scenario_runner.execute_recommendation_review(db, body.sku, body.recommended_qty)
    return agent_run


@router.post("/supplier-shortfall", response_model=AgentRunOut)
def supplier_shortfall(body: SupplierShortfallRequest, db: Session = Depends(get_db)):
    agent_run = scenario_runner.execute_supplier_shortfall(db, body.po_id, body.fulfilled_qty)
    return agent_run
