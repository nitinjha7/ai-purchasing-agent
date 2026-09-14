import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.domain.models import ProposedAction
from app.services import validation_service


@pytest.fixture()
def full_setup(db_session):
    db_session.add(Product(sku="SKU-V", name="V", category="grocery", unit_cost=2.0))
    db_session.add(InventorySnapshot(product_sku="SKU-V", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=900))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=300.0))
    supplier = Supplier(name="S", product_sku="SKU-V", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.9, unit_price=2.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return supplier.id


def test_valid_proposal_passes(db_session, full_setup):
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=60)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is True
    assert verdict.violations == []


def test_below_moq_is_violation(db_session, full_setup):
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=20)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("minimum order" in v.lower() for v in verdict.violations)


def test_exceeds_budget_is_violation(db_session, full_setup):
    # qty 200 * unit_price 2.0 = 400 > available 300
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=200)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("budget" in v.lower() for v in verdict.violations)


def test_exceeds_storage_is_violation(db_session, full_setup):
    # available storage = 1000 - 900 = 100; qty 150 exceeds it
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=150)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("storage" in v.lower() for v in verdict.violations)


def test_non_po_actions_are_always_valid(db_session, full_setup):
    action = ProposedAction(action_type="no_action")
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is True
