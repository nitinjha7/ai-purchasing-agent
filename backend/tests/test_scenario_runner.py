import pytest

from app.db.models import Budget, InventorySnapshot, Product, PurchaseOrder, Supplier
from app.domain.models import AgentDecision, ProposedAction
from app.agent import scenario_runner


@pytest.fixture()
def base_setup(db_session):
    db_session.add(Product(sku="SKU-RUN", name="Run", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-RUN", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-RUN", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.95, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-RUN", supplier.id


def test_execute_recommendation_review_persists_valid_decision(db_session, base_setup, monkeypatch):
    sku, supplier_id = base_setup

    def fake_run_agent(db, scenario_type, situation, revision_note=None):
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=200),
            reasoning="Demand supports this purchase.",
            key_factors=["demand gap", "budget available"],
            confidence=0.9,
        )
        return decision, [{"tool": "get_product_snapshot", "args": {"sku": sku}, "result": {}}]

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_recommendation_review(db_session, sku, recommended_qty=800)

    assert agent_run.decision["decision"] == "accept"
    assert agent_run.validator_verdict["is_valid"] is True
    assert len(agent_run.tool_call_log) == 1


def test_execute_recommendation_review_retries_once_and_persists_revised_decision(db_session, base_setup, monkeypatch):
    """An invalid first proposal is fed back to the agent, which revises it once."""
    sku, supplier_id = base_setup
    calls: list[str | None] = []

    def fake_run_agent(db, scenario_type, situation, revision_note=None):
        calls.append(revision_note)
        if revision_note is None:
            # Below the supplier's minimum order quantity of 50.
            return (
                AgentDecision(
                    decision="accept",
                    proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=10),
                    reasoning="Should be enough.",
                    key_factors=["demand gap"],
                    confidence=0.6,
                ),
                [{"tool": "get_product_snapshot", "args": {"sku": sku}, "result": {}}],
            )
        return (
            AgentDecision(
                decision="modify",
                proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=50),
                reasoning="Raised to the supplier minimum order quantity.",
                key_factors=["minimum order quantity"],
                confidence=0.8,
            ),
            [{"tool": "get_supplier_terms", "args": {"supplier_id": supplier_id}, "result": {}}],
        )

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_recommendation_review(db_session, sku, recommended_qty=10)

    assert len(calls) == 2
    assert calls[0] is None
    assert "minimum order" in calls[1].lower()
    # The persisted decision/verdict are the second attempt's.
    assert agent_run.decision["proposed_action"]["qty"] == 50
    assert agent_run.validator_verdict["is_valid"] is True
    assert agent_run.outcome == "pending_approval"
    # Tool call logs from both attempts are concatenated.
    assert [entry["tool"] for entry in agent_run.tool_call_log] == ["get_product_snapshot", "get_supplier_terms"]


def test_execute_recommendation_review_flags_invalid_proposal_after_single_retry(db_session, base_setup, monkeypatch):
    """If the revision is still invalid, the failure is persisted and no further retry happens."""
    sku, supplier_id = base_setup
    calls: list[str | None] = []

    def fake_run_agent(db, scenario_type, situation, revision_note=None):
        calls.append(revision_note)
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=10),
            reasoning="Should be enough.",
            key_factors=["demand gap"],
            confidence=0.6,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_recommendation_review(db_session, sku, recommended_qty=10)

    assert len(calls) == 2  # exactly one retry, then give up
    assert agent_run.validator_verdict["is_valid"] is False
    assert any("minimum order" in v.lower() for v in agent_run.validator_verdict["violations"])
    assert agent_run.outcome == "validation_failed"


def test_execute_supplier_shortfall_records_shortfall_on_po(db_session, base_setup, monkeypatch):
    sku, supplier_id = base_setup
    po = PurchaseOrder(product_sku=sku, supplier_id=supplier_id, qty=500, status="submitted")
    db_session.add(po)
    db_session.commit()

    def fake_run_agent(db, scenario_type, situation, revision_note=None):
        decision = AgentDecision(
            decision="modify",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=250),
            reasoning="Source remainder from alternate supplier.",
            key_factors=["shortfall", "alternate supplier available"],
            confidence=0.8,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_supplier_shortfall(db_session, po.id, fulfilled_qty=250)

    db_session.refresh(po)
    assert po.fulfilled_qty == 250
    assert po.status == "partially_fulfilled"
    assert agent_run.decision["decision"] == "modify"
