from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import PurchaseOrderOut
from app.services import purchase_order_service

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


class CreateFromProposalRequest(BaseModel):
    sku: str
    supplier_id: int
    qty: int


@router.post("/from-proposal", response_model=PurchaseOrderOut)
def create_purchase_order_from_proposal(body: CreateFromProposalRequest, db: Session = Depends(get_db)):
    return purchase_order_service.create(db, body.sku, body.supplier_id, body.qty)


@router.post("/{po_id}/approve", response_model=PurchaseOrderOut)
def approve_purchase_order(po_id: int, db: Session = Depends(get_db)):
    try:
        return purchase_order_service.approve(db, po_id)
    except purchase_order_service.PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{po_id}/reject", response_model=PurchaseOrderOut)
def reject_purchase_order(po_id: int, db: Session = Depends(get_db)):
    try:
        return purchase_order_service.reject(db, po_id)
    except purchase_order_service.PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
