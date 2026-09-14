from sqlalchemy.orm import Session

from app.db.models import Product
from app.domain.models import ProposedAction, ValidatorVerdict
from app.services import budget_service, inventory_service, purchase_order_service, supplier_service

CURRENT_PERIOD = "2026-09"  # prototype simplification: single active budget period


def _resolve_target(db: Session, action: ProposedAction) -> tuple[str | None, int | None, list[str]]:
    """Resolve the product/supplier the proposal applies to.

    A create_po proposal carries them directly; an amend_po proposal only carries the
    po_id, so they are read off the referenced purchase order.
    """
    if action.action_type != "amend_po":
        return action.product_sku, action.supplier_id, []

    if action.po_id is None:
        return None, None, ["An amend_po proposal must reference an existing purchase order id."]

    try:
        po = purchase_order_service.get(db, action.po_id)
    except purchase_order_service.PurchaseOrderNotFoundError:
        return None, None, [f"No purchase order with id={action.po_id}."]

    return po.product_sku, po.supplier_id, []


def validate_proposal(db: Session, action: ProposedAction) -> ValidatorVerdict:
    if action.action_type not in ("create_po", "amend_po"):
        return ValidatorVerdict(is_valid=True, violations=[])

    violations: list[str] = []

    if action.qty is None or action.qty <= 0:
        violations.append("Quantity must be a positive number.")
        return ValidatorVerdict(is_valid=False, violations=violations)

    product_sku, supplier_id, resolution_violations = _resolve_target(db, action)
    if resolution_violations:
        return ValidatorVerdict(is_valid=False, violations=resolution_violations)
    if product_sku is None or supplier_id is None:
        return ValidatorVerdict(
            is_valid=False,
            violations=["Proposal must identify both a product SKU and a supplier."],
        )

    try:
        supplier = supplier_service.get_terms(db, supplier_id)
    except supplier_service.SupplierNotFoundError:
        return ValidatorVerdict(is_valid=False, violations=[f"No supplier with id={supplier_id}."])

    if action.qty < supplier.min_order_qty:
        violations.append(
            f"Quantity {action.qty} is below supplier minimum order quantity of {supplier.min_order_qty}."
        )

    product = db.get(Product, product_sku)
    if product is None:
        return ValidatorVerdict(is_valid=False, violations=[f"No product with sku={product_sku}."])

    cost = action.qty * supplier.unit_price
    try:
        if not budget_service.has_sufficient_budget(db, product.category, CURRENT_PERIOD, cost):
            available = budget_service.get_status(db, product.category, CURRENT_PERIOD).available_amount
            violations.append(f"Estimated cost {cost:.2f} exceeds available budget {available:.2f} for category '{product.category}'.")
    except budget_service.BudgetNotFoundError:
        violations.append(f"No budget defined for category '{product.category}' in period {CURRENT_PERIOD}.")

    try:
        available_storage = inventory_service.available_storage(db, product_sku)
    except inventory_service.SnapshotNotFoundError:
        violations.append(f"No inventory snapshot for sku={product_sku}; storage capacity cannot be checked.")
    else:
        if action.qty > available_storage:
            violations.append(f"Quantity {action.qty} exceeds available storage capacity of {available_storage} units.")

    return ValidatorVerdict(is_valid=len(violations) == 0, violations=violations)
