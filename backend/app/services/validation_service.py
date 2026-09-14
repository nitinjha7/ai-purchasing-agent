from sqlalchemy.orm import Session

from app.db.models import Product
from app.domain.models import ProposedAction, ValidatorVerdict
from app.services import budget_service, inventory_service, supplier_service

CURRENT_PERIOD = "2026-09"  # prototype simplification: single active budget period


def validate_proposal(db: Session, action: ProposedAction) -> ValidatorVerdict:
    if action.action_type not in ("create_po", "amend_po"):
        return ValidatorVerdict(is_valid=True, violations=[])

    violations: list[str] = []

    if action.qty is None or action.qty <= 0:
        violations.append("Quantity must be a positive number.")
        return ValidatorVerdict(is_valid=False, violations=violations)

    supplier = supplier_service.get_terms(db, action.supplier_id)
    if action.qty < supplier.min_order_qty:
        violations.append(
            f"Quantity {action.qty} is below supplier minimum order quantity of {supplier.min_order_qty}."
        )

    product = db.get(Product, action.product_sku)
    cost = action.qty * supplier.unit_price
    if not budget_service.has_sufficient_budget(db, product.category, CURRENT_PERIOD, cost):
        available = budget_service.get_status(db, product.category, CURRENT_PERIOD).available_amount
        violations.append(f"Estimated cost {cost:.2f} exceeds available budget {available:.2f} for category '{product.category}'.")

    available_storage = inventory_service.available_storage(db, action.product_sku)
    if action.qty > available_storage:
        violations.append(f"Quantity {action.qty} exceeds available storage capacity of {available_storage} units.")

    return ValidatorVerdict(is_valid=len(violations) == 0, violations=violations)
