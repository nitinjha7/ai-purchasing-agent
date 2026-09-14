from sqlalchemy.orm import Session

from app.db.models import Budget
from app.domain.models import BudgetOut


class BudgetNotFoundError(Exception):
    pass


def get_status(db: Session, category: str, period: str) -> BudgetOut:
    row = db.get(Budget, {"category": category, "period": period})
    if row is None:
        raise BudgetNotFoundError(f"No budget for category={category} period={period}")
    return BudgetOut.model_validate(row)


def has_sufficient_budget(db: Session, category: str, period: str, cost: float) -> bool:
    status = get_status(db, category, period)
    return status.available_amount >= cost
