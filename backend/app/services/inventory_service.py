from sqlalchemy.orm import Session

from app.db.models import InventorySnapshot
from app.domain.models import InventorySnapshotOut


class SnapshotNotFoundError(Exception):
    pass


def get_snapshot(db: Session, sku: str) -> InventorySnapshotOut:
    row = db.get(InventorySnapshot, sku)
    if row is None:
        raise SnapshotNotFoundError(f"No inventory snapshot for sku={sku}")
    return InventorySnapshotOut.model_validate(row)


def available_storage(db: Session, sku: str) -> int:
    snapshot = get_snapshot(db, sku)
    return snapshot.available_storage_units
