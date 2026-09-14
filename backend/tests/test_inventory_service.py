import pytest

from app.db.models import InventorySnapshot, Product
from app.services import inventory_service


@pytest.fixture()
def product_with_stock(db_session):
    db_session.add(Product(sku="SKU-X", name="X", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-X", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=800))
    db_session.commit()
    return "SKU-X"


def test_get_snapshot_returns_data(db_session, product_with_stock):
    snapshot = inventory_service.get_snapshot(db_session, product_with_stock)
    assert snapshot.on_hand_qty == 100


def test_available_storage_computes_remaining_capacity(db_session, product_with_stock):
    assert inventory_service.available_storage(db_session, product_with_stock) == 200


def test_get_snapshot_missing_sku_raises(db_session):
    with pytest.raises(inventory_service.SnapshotNotFoundError):
        inventory_service.get_snapshot(db_session, "NOPE")
