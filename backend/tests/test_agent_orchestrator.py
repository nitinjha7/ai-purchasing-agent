import os

import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.agent.orchestrator import run_agent

requires_real_gemini_key = pytest.mark.skipif(
    os.environ.get("GEMINI_API_KEY", "test-key-placeholder") == "test-key-placeholder",
    reason="Requires a real GEMINI_API_KEY to call the live API",
)


@pytest.fixture()
def clean_accept_scenario(db_session):
    db_session.add(Product(sku="SKU-ORCH", name="Orch", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-ORCH", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-ORCH", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.95, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-ORCH"


@requires_real_gemini_key
def test_run_agent_returns_decision_for_recommendation_review(db_session, clean_accept_scenario):
    decision, tool_log = run_agent(
        db_session, "recommendation_review",
        {"sku": clean_accept_scenario, "recommended_qty": 100},
    )

    assert decision.decision in ("accept", "modify", "reject", "investigate")
    assert len(tool_log) > 0
    assert any(entry["tool"] == "get_product_snapshot" for entry in tool_log)
