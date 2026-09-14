from sqlalchemy.orm import Session

from app.db.models import DemandForecast, InventorySnapshot, PurchaseOrder
from app.domain.models import DemandForecastOut


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
    open_qty = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.product_sku == sku, PurchaseOrder.status.in_(["draft", "pending_approval", "approved", "submitted"]))
        .with_entities(PurchaseOrder.qty)
        .all()
    )
    open_total = sum(qty for (qty,) in open_qty)
    return forecast.forecast_qty - on_hand - open_total
