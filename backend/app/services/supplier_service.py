from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder, Supplier
from app.domain.models import SupplierOut


class SupplierNotFoundError(Exception):
    pass


class PurchaseOrderNotFoundError(Exception):
    pass


@dataclass
class FulfillmentResult:
    fulfilled_qty: int
    status: Literal["fulfilled", "partially_fulfilled"]


def get_terms(db: Session, supplier_id: int) -> SupplierOut:
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise SupplierNotFoundError(f"No supplier with id={supplier_id}")
    return SupplierOut.model_validate(row)


def list_alternates(db: Session, sku: str, exclude_supplier_id: int | None = None) -> list[SupplierOut]:
    query = db.query(Supplier).filter(Supplier.product_sku == sku)
    if exclude_supplier_id is not None:
        query = query.filter(Supplier.id != exclude_supplier_id)
    return [SupplierOut.model_validate(row) for row in query.order_by(Supplier.id).all()]


def submit_to_supplier(db: Session, po_id: int) -> FulfillmentResult:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise PurchaseOrderNotFoundError(f"No purchase order with id={po_id}")

    supplier = db.get(Supplier, po.supplier_id)
    cap = supplier.fulfillment_cap_qty
    fulfilled = min(po.qty, cap) if cap is not None else po.qty
    status: Literal["fulfilled", "partially_fulfilled"] = "fulfilled" if fulfilled >= po.qty else "partially_fulfilled"

    po.fulfilled_qty = fulfilled
    po.status = status
    db.commit()

    return FulfillmentResult(fulfilled_qty=fulfilled, status=status)
