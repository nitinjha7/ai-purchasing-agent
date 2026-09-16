from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Budget, DemandForecast, InventorySnapshot, Product, PurchaseOrder, Supplier

# SKU-100: healthy budget/storage, used for the clean-accept eval case
# SKU-200: tight budget, used for budget-constrained cases
# SKU-300: tight storage, used for storage-constrained cases


def seed(db: Session) -> None:
    products = [
        Product(sku="SKU-100", name="Instant Noodles 500g", category="grocery", unit_cost=1.20),
        Product(sku="SKU-200", name="Premium Olive Oil 1L", category="grocery", unit_cost=8.50),
        Product(sku="SKU-300", name="Paper Towels 6-pack", category="household", unit_cost=3.00),
    ]
    db.add_all(products)
    # Flushed separately: no relationship() links Product to the tables below, so
    # SQLAlchemy can't infer insert ordering across them in one flush, and Postgres
    # (unlike SQLite, which ignores FK violations by default) enforces the order.
    db.flush()

    db.add_all([
        InventorySnapshot(product_sku="SKU-100", on_hand_qty=200, storage_capacity_units=5000, storage_used_units=1000),
        InventorySnapshot(product_sku="SKU-200", on_hand_qty=50, storage_capacity_units=2000, storage_used_units=300),
        InventorySnapshot(product_sku="SKU-300", on_hand_qty=100, storage_capacity_units=900, storage_used_units=850),
    ])

    db.add_all([
        DemandForecast(product_sku="SKU-100", horizon_days=30, forecast_qty=600, recent_actual_sales_qty=580),
        DemandForecast(product_sku="SKU-200", horizon_days=30, forecast_qty=400, recent_actual_sales_qty=410),
        DemandForecast(product_sku="SKU-300", horizon_days=30, forecast_qty=300, recent_actual_sales_qty=290),
    ])

    db.add_all([
        Supplier(name="Northwind Foods", product_sku="SKU-100", lead_time_days=7, min_order_qty=100,
                  reliability_score=0.95, unit_price=1.10, fulfillment_cap_qty=None),
        Supplier(name="Northwind Backup", product_sku="SKU-100", lead_time_days=10, min_order_qty=50,
                  reliability_score=0.88, unit_price=1.18, fulfillment_cap_qty=None),
        Supplier(name="MedOil Traders", product_sku="SKU-200", lead_time_days=14, min_order_qty=200,
                  reliability_score=0.80, unit_price=8.20, fulfillment_cap_qty=250),
        Supplier(name="MedOil Alt Source", product_sku="SKU-200", lead_time_days=5, min_order_qty=100,
                  reliability_score=0.90, unit_price=8.60, fulfillment_cap_qty=None),
        Supplier(name="PaperCo", product_sku="SKU-300", lead_time_days=4, min_order_qty=150,
                  reliability_score=0.92, unit_price=2.90, fulfillment_cap_qty=None),
    ])

    db.add_all([
        Budget(category="grocery", period="2026-09", available_amount=1500.0),
        Budget(category="household", period="2026-09", available_amount=500.0),
    ])

    db.flush()

    db.add(PurchaseOrder(
        product_sku="SKU-200", supplier_id=3, qty=500, fulfilled_qty=0, status="submitted",
        expected_arrival=datetime.now(timezone.utc) + timedelta(days=14),
    ))

    db.commit()
