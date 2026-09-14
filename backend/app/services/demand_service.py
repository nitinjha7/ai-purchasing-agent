from sqlalchemy.orm import Session

from app.db.models import DemandForecast, InventorySnapshot, PurchaseOrder
from app.domain.models import DemandForecastOut
from app.services.purchase_order_service import OPEN_STATUSES


class ForecastNotFoundError(Exception):
    pass


def get_forecast(db: Session, sku: str) -> DemandForecastOut:
    row = db.get(DemandForecast, sku)
    if row is None:
        raise ForecastNotFoundError(f"No demand forecast for sku={sku}")
    return DemandForecastOut.model_validate(row)


def net_demand_gap(db: Session, sku: str) -> int:
    forecast = get_forecast(db, sku)
    snapshot = db.get(InventorySnapshot, sku)
    on_hand = snapshot.on_hand_qty if snapshot else 0
    open_rows = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.product_sku == sku,
            PurchaseOrder.status.in_([s.value for s in OPEN_STATUSES]),
        )
        .with_entities(PurchaseOrder.qty, PurchaseOrder.fulfilled_qty)
        .all()
    )
    # Only the still-outstanding portion of an open PO counts as incoming supply: a
    # partially fulfilled PO has already delivered fulfilled_qty into on-hand stock.
    open_total = sum(max(qty - (fulfilled_qty or 0), 0) for qty, fulfilled_qty in open_rows)
    return forecast.forecast_qty - on_hand - open_total
