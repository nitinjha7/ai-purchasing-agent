from fastapi.testclient import TestClient

from app.agent import scenario_runner
from app.db.base import Base
from app.db.models import AgentRun
from app.domain.models import AgentDecision, ProposedAction
from app.main import app


def test_recommendation_review_endpoint_returns_agent_run(monkeypatch, db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    from app.db.models import Budget, InventorySnapshot, Product, Supplier
    db_session.add(Product(sku="SKU-API", name="Api", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-API", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-API", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()

    def fake_run_agent_for_scenario(db, scenario_type, situation):
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku="SKU-API", supplier_id=supplier.id, qty=200),
            reasoning="ok", key_factors=["x"], confidence=0.9,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent_for_scenario)

    client = TestClient(app)
    response = client.post("/api/scenarios/recommendation-review", json={"sku": "SKU-API", "recommended_qty": 800})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "accept"

    app.dependency_overrides.clear()


def test_create_purchase_order_from_proposal_endpoint(db_session):
    from app.api import deps
    from app.db.models import Product, Supplier

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    db_session.add(Product(sku="SKU-PROP", name="Prop", category="general", unit_cost=1.0))
    supplier = Supplier(name="S", product_sku="SKU-PROP", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"sku": "SKU-PROP", "supplier_id": supplier.id, "qty": 100})

    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"

    app.dependency_overrides.clear()
