from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.db.models import AgentRun, PurchaseOrder
from app.domain.models import AgentDecision, ValidatorVerdict
from app.services import validation_service


def run_agent_for_scenario(
    db: Session,
    scenario_type: str,
    situation: dict,
    revision_note: str | None = None,
) -> tuple[AgentDecision, list[dict]]:
    return run_agent(db, scenario_type, situation, revision_note=revision_note)


def _validate(db: Session, decision: AgentDecision) -> ValidatorVerdict | None:
    if decision.proposed_action is None:
        return None
    return validation_service.validate_proposal(db, decision.proposed_action)


def _build_revision_note(verdict: ValidatorVerdict) -> str:
    return (
        f"Your previous proposal was rejected for these reasons: {'; '.join(verdict.violations)}. "
        "Please revise your proposal to address them, or choose a different decision "
        "(e.g. reject or investigate) if no valid proposal is possible."
    )


def _decide_with_one_revision(
    db: Session, scenario_type: str, situation: dict
) -> tuple[AgentDecision, list[dict], ValidatorVerdict | None]:
    """Run the agent, and if the validator rejects its proposal, feed the violations back
    and let it revise exactly once before giving up."""
    decision, tool_call_log = run_agent_for_scenario(db, scenario_type, situation)
    verdict = _validate(db, decision)

    if verdict is not None and not verdict.is_valid:
        decision, revision_log = run_agent_for_scenario(
            db, scenario_type, situation, revision_note=_build_revision_note(verdict)
        )
        tool_call_log = list(tool_call_log) + list(revision_log)
        verdict = _validate(db, decision)

    return decision, tool_call_log, verdict


def _persist(
    db: Session,
    scenario_type: str,
    situation: dict,
    decision: AgentDecision,
    tool_call_log: list[dict],
    verdict: ValidatorVerdict | None,
) -> AgentRun:
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
    decision, tool_call_log, verdict = _decide_with_one_revision(db, "recommendation_review", situation)
    return _persist(db, "recommendation_review", situation, decision, tool_call_log, verdict)


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
    decision, tool_call_log, verdict = _decide_with_one_revision(db, "supplier_shortfall", situation)
    return _persist(db, "supplier_shortfall", situation, decision, tool_call_log, verdict)
