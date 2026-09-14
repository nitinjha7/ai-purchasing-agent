import pytest

from app.db.models import Product, Supplier
from app.domain.models import PurchaseOrderStatus
from app.services import purchase_order_service as po_service


@pytest.fixture()
def sku_and_supplier(db_session):
    db_session.add(Product(sku="SKU-P", name="P", category="general", unit_cost=1.0))
    supplier = Supplier(name="S1", product_sku="SKU-P", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-P", supplier.id


def test_create_starts_pending_approval(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    assert po.status == PurchaseOrderStatus.PENDING_APPROVAL
    assert po.qty == 100


def test_amend_changes_qty(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    amended = po_service.amend(db_session, po.id, new_qty=150)
    assert amended.qty == 150


def test_approve_submits_and_updates_status(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    approved = po_service.approve(db_session, po.id)
    assert approved.status == PurchaseOrderStatus.FULFILLED
    assert approved.fulfilled_qty == 100


def test_reject_sets_status(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    rejected = po_service.reject(db_session, po.id)
    assert rejected.status == PurchaseOrderStatus.REJECTED


def test_get_open_pos_excludes_terminal_statuses(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    open_po = po_service.create(db_session, sku, supplier_id, qty=100)
    closed_po = po_service.create(db_session, sku, supplier_id, qty=50)
    po_service.reject(db_session, closed_po.id)

    open_pos = po_service.get_open_pos(db_session, sku)

    assert [p.id for p in open_pos] == [open_po.id]
