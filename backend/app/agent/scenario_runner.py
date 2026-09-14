from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.db.models import AgentRun, PurchaseOrder
from app.domain.models import AgentDecision
from app.services import validation_service


def run_agent_for_scenario(db: Session, scenario_type: str, situation: dict) -> tuple[AgentDecision, list[dict]]:
    return run_agent(db, scenario_type, situation)


def _validate_and_persist(db: Session, scenario_type: str, situation: dict, decision: AgentDecision, tool_call_log: list[dict]) -> AgentRun:
    verdict = None
    if decision.proposed_action is not None:
        verdict = validation_service.validate_proposal(db, decision.proposed_action)

    agent_run = AgentRun(
        scenario_type=scenario_type,
        input_situation=situation,
        tool_call_log=tool_call_log,
        decision=decision.model_dump(mode="json"),
        validator_verdict=verdict.model_dump() if verdict else None,
        outcome="pending_approval" if verdict is None or verdict.is_valid else "validation_failed",
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)
    return agent_run


def execute_recommendation_review(db: Session, sku: str, recommended_qty: int) -> AgentRun:
    situation = {"sku": sku, "recommended_qty": recommended_qty}
    decision, tool_call_log = run_agent_for_scenario(db, "recommendation_review", situation)
    return _validate_and_persist(db, "recommendation_review", situation, decision, tool_call_log)


def execute_supplier_shortfall(db: Session, po_id: int, fulfilled_qty: int) -> AgentRun:
    po = db.get(PurchaseOrder, po_id)
    po.fulfilled_qty = fulfilled_qty
    po.status = "partially_fulfilled" if fulfilled_qty < po.qty else "fulfilled"
    db.commit()

    situation = {
        "po_id": po_id,
        "sku": po.product_sku,
        "supplier_id": po.supplier_id,
        "ordered_qty": po.qty,
        "fulfilled_qty": fulfilled_qty,
    }
    decision, tool_call_log = run_agent_for_scenario(db, "supplier_shortfall", situation)
    return _validate_and_persist(db, "supplier_shortfall", situation, decision, tool_call_log)
