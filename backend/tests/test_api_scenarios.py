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

    def fake_run_agent_for_scenario(db, scenario_type, situation, revision_note=None):
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


def _seed_catalog(db_session):
    """Seed (once per session) the product/inventory/budget/supplier used by proposal tests."""
    from app.db.models import Budget, InventorySnapshot, Product, Supplier

    Base.metadata.create_all(bind=db_session.get_bind())
    existing = db_session.query(Supplier).filter(Supplier.product_sku == "SKU-PROP").first()
    if existing is not None:
        return existing

    db_session.add(Product(sku="SKU-PROP", name="Prop", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-PROP", on_hand_qty=0, storage_capacity_units=5000, storage_used_units=0))
    db_session.add(Budget(category="general", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-PROP", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return supplier


def _proposal_setup(db_session, qty: int, action_type: str = "create_po", po_id: int | None = None):
    """Seed the catalog plus an agent run holding a proposal of the given shape."""
    supplier = _seed_catalog(db_session)

    proposed_action = {
        "action_type": action_type,
        "product_sku": "SKU-PROP" if action_type == "create_po" else None,
        "supplier_id": supplier.id if action_type == "create_po" else None,
        "qty": qty,
        "po_id": po_id,
    }
    run = AgentRun(
        scenario_type="recommendation_review",
        input_situation={"sku": "SKU-PROP", "recommended_qty": qty},
        tool_call_log=[],
        decision={
            "decision": "accept",
            "proposed_action": proposed_action,
            "reasoning": "ok",
            "key_factors": ["x"],
            "confidence": 0.9,
        },
        validator_verdict={"is_valid": True, "violations": []},
        outcome="pending_approval",
    )
    db_session.add(run)
    db_session.commit()
    return supplier, run


def test_create_purchase_order_from_proposal_endpoint(db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    _supplier, run = _proposal_setup(db_session, qty=100)

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"agent_run_id": run.id})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["qty"] == 100
    assert body["product_sku"] == "SKU-PROP"

    db_session.refresh(run)
    assert run.human_action == "approved"

    app.dependency_overrides.clear()


def test_create_purchase_order_from_proposal_rejects_unknown_agent_run(db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"agent_run_id": 9999})

    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_create_purchase_order_from_proposal_revalidates_server_side(db_session):
    """A stored verdict is never trusted: the proposal is re-validated at approval time."""
    from app.api import deps
    from app.db.models import PurchaseOrder

    app.dependency_overrides[deps.get_db] = lambda: db_session
    # qty 5 is below the supplier's min_order_qty of 10, but the run claims it is valid.
    _supplier, run = _proposal_setup(db_session, qty=5)

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"agent_run_id": run.id})

    assert response.status_code == 400
    assert any("minimum order" in v.lower() for v in response.json()["detail"]["violations"])
    assert db_session.query(PurchaseOrder).count() == 0

    db_session.refresh(run)
    assert run.human_action is None

    app.dependency_overrides.clear()


def test_amend_purchase_order_from_proposal_endpoint(db_session):
    from app.api import deps
    from app.db.models import PurchaseOrder

    app.dependency_overrides[deps.get_db] = lambda: db_session
    supplier = _seed_catalog(db_session)
    po = PurchaseOrder(product_sku="SKU-PROP", supplier_id=supplier.id, qty=100, status="submitted")
    db_session.add(po)
    db_session.commit()

    _supplier, amend_run = _proposal_setup(db_session, qty=250, action_type="amend_po", po_id=po.id)

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-amend-proposal", json={"agent_run_id": amend_run.id})

    assert response.status_code == 200
    assert response.json()["qty"] == 250

    db_session.refresh(amend_run)
    assert amend_run.human_action == "approved"

    app.dependency_overrides.clear()


def test_from_proposal_rejects_mismatched_action_type(db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    _supplier, run = _proposal_setup(db_session, qty=100, action_type="amend_po", po_id=1)

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"agent_run_id": run.id})

    assert response.status_code == 400
    assert "amend_po" in response.json()["detail"]

    app.dependency_overrides.clear()


def test_reject_agent_run_records_rejection_without_creating_a_po(db_session):
    from app.api import deps
    from app.db.models import PurchaseOrder

    app.dependency_overrides[deps.get_db] = lambda: db_session
    _supplier, run = _proposal_setup(db_session, qty=100)

    client = TestClient(app)
    response = client.post(f"/api/agent-runs/{run.id}/reject")

    assert response.status_code == 200
    assert response.json()["human_action"] == "rejected"
    assert db_session.query(PurchaseOrder).count() == 0

    app.dependency_overrides.clear()


def test_reject_unknown_agent_run_returns_404(db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    client = TestClient(app)
    assert client.post("/api/agent-runs/9999/reject").status_code == 404

    app.dependency_overrides.clear()


def test_approve_partially_fulfilled_po_reinvokes_the_agent(db_session, monkeypatch):
    """The mock ERP's partial fulfillment automatically triggers a shortfall agent run."""
    from app.api import deps
    from app.db.models import Budget, InventorySnapshot, Product, PurchaseOrder, Supplier

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    db_session.add(Product(sku="SKU-CAP", name="Cap", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-CAP", on_hand_qty=0, storage_capacity_units=5000, storage_used_units=0))
    db_session.add(Budget(category="general", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="Capped", product_sku="SKU-CAP", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=250)
    db_session.add(supplier)
    db_session.commit()
    po = PurchaseOrder(product_sku="SKU-CAP", supplier_id=supplier.id, qty=500, status="pending_approval")
    db_session.add(po)
    db_session.commit()

    def fake_run_agent_for_scenario(db, scenario_type, situation, revision_note=None):
        decision = AgentDecision(
            decision="modify",
            proposed_action=ProposedAction(action_type="create_po", product_sku="SKU-CAP", supplier_id=supplier.id, qty=250),
            reasoning="Source the remainder elsewhere.",
            key_factors=["shortfall"],
            confidence=0.8,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent_for_scenario)

    client = TestClient(app)
    response = client.post(f"/api/purchase-orders/{po.id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "partially_fulfilled"

    runs = db_session.query(AgentRun).filter(AgentRun.scenario_type == "supplier_shortfall").all()
    assert len(runs) == 1
    assert runs[0].input_situation["fulfilled_qty"] == 250

    app.dependency_overrides.clear()
