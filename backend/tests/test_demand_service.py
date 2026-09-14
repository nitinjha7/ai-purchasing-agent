import pytest

from app.db.models import DemandForecast, InventorySnapshot, Product, PurchaseOrder, Supplier
from app.services import demand_service


@pytest.fixture()
def product_with_demand_and_open_po(db_session):
    db_session.add(Product(sku="SKU-Y", name="Y", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-Y", on_hand_qty=50, storage_capacity_units=1000, storage_used_units=100))
    db_session.add(DemandForecast(product_sku="SKU-Y", horizon_days=30, forecast_qty=300, recent_actual_sales_qty=310))
    supplier = Supplier(name="S", product_sku="SKU-Y", lead_time_days=5, min_order_qty=10, reliability_score=0.9, unit_price=1.0)
    db_session.add(supplier)
    db_session.flush()
    db_session.add(PurchaseOrder(product_sku="SKU-Y", supplier_id=supplier.id, qty=100, status="submitted"))
    db_session.commit()
    return "SKU-Y"


def test_get_forecast_returns_data(db_session, product_with_demand_and_open_po):
    forecast = demand_service.get_forecast(db_session, product_with_demand_and_open_po)
    assert forecast.forecast_qty == 300


def test_net_demand_gap_subtracts_on_hand_and_open_pos(db_session, product_with_demand_and_open_po):
    # forecast 300 - on_hand 50 - open_po 100 = 150
    assert demand_service.net_demand_gap(db_session, product_with_demand_and_open_po) == 150
