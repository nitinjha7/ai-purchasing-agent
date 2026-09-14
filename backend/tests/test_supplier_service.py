import pytest

from app.db.models import Product, PurchaseOrder, Supplier
from app.services import supplier_service


@pytest.fixture()
def two_suppliers_one_capped(db_session):
    db_session.add(Product(sku="SKU-Z", name="Z", category="general", unit_cost=2.0))
    db_session.add(Supplier(name="Capped", product_sku="SKU-Z", lead_time_days=10, min_order_qty=50,
                             reliability_score=0.7, unit_price=2.0, fulfillment_cap_qty=250))
    db_session.add(Supplier(name="Uncapped", product_sku="SKU-Z", lead_time_days=6, min_order_qty=20,
                             reliability_score=0.95, unit_price=2.2, fulfillment_cap_qty=None))
    db_session.commit()
    suppliers = db_session.query(Supplier).order_by(Supplier.id).all()
    return suppliers[0], suppliers[1]


def test_get_terms_returns_data(db_session, two_suppliers_one_capped):
    capped, _ = two_suppliers_one_capped
    terms = supplier_service.get_terms(db_session, capped.id)
    assert terms.min_order_qty == 50


def test_list_alternates_excludes_given_supplier(db_session, two_suppliers_one_capped):
    capped, uncapped = two_suppliers_one_capped
    alternates = supplier_service.list_alternates(db_session, "SKU-Z", exclude_supplier_id=capped.id)
    assert [a.id for a in alternates] == [uncapped.id]


def test_submit_to_supplier_caps_fulfillment(db_session, two_suppliers_one_capped):
    capped, _ = two_suppliers_one_capped
    po = PurchaseOrder(product_sku="SKU-Z", supplier_id=capped.id, qty=500, status="approved")
    db_session.add(po)
    db_session.commit()

    result = supplier_service.submit_to_supplier(db_session, po.id)

    assert result.fulfilled_qty == 250
    assert result.status == "partially_fulfilled"
    db_session.refresh(po)
    assert po.fulfilled_qty == 250
    assert po.status == "partially_fulfilled"


def test_submit_to_supplier_fulfills_in_full_when_uncapped(db_session, two_suppliers_one_capped):
    _, uncapped = two_suppliers_one_capped
    po = PurchaseOrder(product_sku="SKU-Z", supplier_id=uncapped.id, qty=100, status="approved")
    db_session.add(po)
    db_session.commit()

    result = supplier_service.submit_to_supplier(db_session, po.id)

    assert result.fulfilled_qty == 100
    assert result.status == "fulfilled"
