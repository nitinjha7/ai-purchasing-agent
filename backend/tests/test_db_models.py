from app.db.models import Product, Supplier, PurchaseOrder


def test_create_product_and_supplier_and_po(db_session):
    product = Product(sku="SKU-1", name="Widget", category="general", unit_cost=10.0)
    db_session.add(product)
    db_session.flush()

    supplier = Supplier(
        name="Acme", product_sku="SKU-1", lead_time_days=5,
        min_order_qty=50, reliability_score=0.9, unit_price=9.5,
    )
    db_session.add(supplier)
    db_session.flush()

    po = PurchaseOrder(product_sku="SKU-1", supplier_id=supplier.id, qty=100)
    db_session.add(po)
    db_session.commit()

    assert po.id is not None
    assert po.status == "draft"
