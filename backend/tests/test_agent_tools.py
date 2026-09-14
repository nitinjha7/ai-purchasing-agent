import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.agent import tools


@pytest.fixture()
def seeded(db_session):
    db_session.add(Product(sku="SKU-T", name="T", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-T", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=200))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=1000.0))
    supplier = Supplier(name="S", product_sku="SKU-T", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-T", supplier.id


def test_dispatch_get_product_snapshot(db_session, seeded):
    sku, _ = seeded
    result = tools.dispatch_tool_call(db_session, "get_product_snapshot", {"sku": sku})
    assert result["on_hand_qty"] == 100


def test_dispatch_propose_purchase_order_does_not_write_to_db(db_session, seeded):
    from app.services import purchase_order_service

    sku, supplier_id = seeded
    result = tools.dispatch_tool_call(
        db_session, "propose_purchase_order",
        {"sku": sku, "supplier_id": supplier_id, "qty": 200, "rationale": "test"},
    )
    assert result["action_type"] == "create_po"
    assert result["qty"] == 200
    assert purchase_order_service.get_open_pos(db_session, sku) == []


def test_dispatch_unknown_tool_raises(db_session, seeded):
    with pytest.raises(tools.UnknownToolError):
        tools.dispatch_tool_call(db_session, "not_a_tool", {})
