from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder
from app.domain.models import PurchaseOrderOut, PurchaseOrderStatus
from app.services import supplier_service

OPEN_STATUSES = {
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PENDING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.SUBMITTED,
    PurchaseOrderStatus.PARTIALLY_FULFILLED,
}


class PurchaseOrderNotFoundError(Exception):
    pass


def _get_row(db: Session, po_id: int) -> PurchaseOrder:
    row = db.get(PurchaseOrder, po_id)
    if row is None:
        raise PurchaseOrderNotFoundError(f"No purchase order with id={po_id}")
    return row


def get(db: Session, po_id: int) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(_get_row(db, po_id))


def create(db: Session, sku: str, supplier_id: int, qty: int) -> PurchaseOrderOut:
    po = PurchaseOrder(product_sku=sku, supplier_id=supplier_id, qty=qty, status=PurchaseOrderStatus.PENDING_APPROVAL)
    db.add(po)
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def amend(db: Session, po_id: int, new_qty: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.qty = new_qty
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def approve(db: Session, po_id: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.status = PurchaseOrderStatus.APPROVED
    db.commit()

    supplier_service.submit_to_supplier(db, po_id)

    db.refresh(po)
    return PurchaseOrderOut.model_validate(po)


def reject(db: Session, po_id: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.status = PurchaseOrderStatus.REJECTED
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def get_open_pos(db: Session, sku: str) -> list[PurchaseOrderOut]:
    rows = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.product_sku == sku, PurchaseOrder.status.in_([s.value for s in OPEN_STATUSES]))
        .order_by(PurchaseOrder.id)
        .all()
    )
    return [PurchaseOrderOut.model_validate(r) for r in rows]
