from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import scenario_runner
from app.api.deps import get_db
from app.db.models import AgentRun
from app.domain.models import ProposedAction, PurchaseOrderOut, PurchaseOrderStatus
from app.services import purchase_order_service, validation_service

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


class FromProposalRequest(BaseModel):
    agent_run_id: int


def _load_validated_proposal(db: Session, agent_run_id: int, expected_action_type: str) -> tuple[AgentRun, ProposedAction]:
    """Re-derive a proposal from its stored agent run and re-validate it server-side.

    The client only supplies an agent run id — quantities, SKUs and suppliers always come
    from the run's own persisted proposal, and the validator verdict is recomputed here
    rather than trusting the one stored at proposal time.
    """
    agent_run = db.get(AgentRun, agent_run_id)
    if agent_run is None:
        raise HTTPException(status_code=404, detail=f"No agent run with id={agent_run_id}")

    raw_action = (agent_run.decision or {}).get("proposed_action")
    if raw_action is None:
        raise HTTPException(status_code=400, detail=f"Agent run {agent_run_id} has no proposed action to execute.")

    action = ProposedAction.model_validate(raw_action)
    if action.action_type != expected_action_type:
        raise HTTPException(
            status_code=400,
            detail=f"Agent run {agent_run_id} proposes '{action.action_type}', not '{expected_action_type}'.",
        )

    verdict = validation_service.validate_proposal(db, action)
    if not verdict.is_valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Proposal failed validation and cannot be executed.", "violations": verdict.violations},
        )

    return agent_run, action


@router.post("/from-proposal", response_model=PurchaseOrderOut)
def create_purchase_order_from_proposal(body: FromProposalRequest, db: Session = Depends(get_db)):
    agent_run, action = _load_validated_proposal(db, body.agent_run_id, "create_po")
    po = purchase_order_service.create(db, action.product_sku, action.supplier_id, action.qty)
    agent_run.human_action = "approved"
    db.commit()
    return po


@router.post("/from-amend-proposal", response_model=PurchaseOrderOut)
def amend_purchase_order_from_proposal(body: FromProposalRequest, db: Session = Depends(get_db)):
    agent_run, action = _load_validated_proposal(db, body.agent_run_id, "amend_po")
    try:
        po = purchase_order_service.amend(db, action.po_id, action.qty)
    except purchase_order_service.PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    agent_run.human_action = "approved"
    db.commit()
    return po


@router.post("/{po_id}/approve", response_model=PurchaseOrderOut)
def approve_purchase_order(po_id: int, db: Session = Depends(get_db)):
    try:
        po = purchase_order_service.approve(db, po_id)
    except purchase_order_service.PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Feedback loop: a partial fulfillment from the mock ERP re-invokes the agent with the
    # updated situation, producing a new agent run for the buyer to review.
    if po.status == PurchaseOrderStatus.PARTIALLY_FULFILLED:
        scenario_runner.execute_supplier_shortfall(db, po_id, fulfilled_qty=po.fulfilled_qty)

    return po


@router.post("/{po_id}/reject", response_model=PurchaseOrderOut)
def reject_purchase_order(po_id: int, db: Session = Depends(get_db)):
    try:
        return purchase_order_service.reject(db, po_id)
    except purchase_order_service.PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
