from typing import Any

from sqlalchemy.orm import Session

from app.services import budget_service, demand_service, inventory_service, purchase_order_service, supplier_service

TOOL_FUNCTION_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "get_product_snapshot",
        "description": "Get current inventory on-hand quantity and storage usage for a product SKU.",
        "parameters": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "get_demand_forecast",
        "description": "Get demand forecast and recent actual sales for a product SKU, plus the net demand gap after accounting for on-hand stock and open purchase orders.",
        "parameters": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "get_open_purchase_orders",
        "description": "List open (not yet fulfilled, rejected, or cancelled) purchase orders for a product SKU.",
        "parameters": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "get_supplier_terms",
        "description": "Get lead time, minimum order quantity, reliability score, and unit price for a supplier.",
        "parameters": {
            "type": "object",
            "properties": {"supplier_id": {"type": "integer"}},
            "required": ["supplier_id"],
        },
    },
    {
        "name": "get_budget_status",
        "description": "Get available purchasing budget for a product category in the current period.",
        "parameters": {
            "type": "object",
            "properties": {"category": {"type": "string"}},
            "required": ["category"],
        },
    },
    {
        "name": "list_alternate_suppliers",
        "description": "List suppliers other than the given one that can supply a product SKU.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "exclude_supplier_id": {"type": "integer"},
            },
            "required": ["sku"],
        },
    },
    {
        "name": "propose_purchase_order",
        "description": "Propose creating a new purchase order. Does not write to the database — the result is validated and requires human approval before execution.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "supplier_id": {"type": "integer"},
                "qty": {"type": "integer"},
                "rationale": {"type": "string"},
            },
            "required": ["sku", "supplier_id", "qty", "rationale"],
        },
    },
    {
        "name": "propose_po_amendment",
        "description": "Propose amending an existing purchase order's quantity. Does not write to the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_id": {"type": "integer"},
                "new_qty": {"type": "integer"},
                "rationale": {"type": "string"},
            },
            "required": ["po_id", "new_qty", "rationale"],
        },
    },
]


class UnknownToolError(Exception):
    pass


def dispatch_tool_call(db: Session, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "get_product_snapshot":
        return inventory_service.get_snapshot(db, args["sku"]).model_dump()
    if name == "get_demand_forecast":
        forecast = demand_service.get_forecast(db, args["sku"])
        gap = demand_service.net_demand_gap(db, args["sku"])
        return {**forecast.model_dump(), "net_demand_gap": gap}
    if name == "get_open_purchase_orders":
        return {"open_purchase_orders": [po.model_dump(mode="json") for po in purchase_order_service.get_open_pos(db, args["sku"])]}
    if name == "get_supplier_terms":
        return supplier_service.get_terms(db, args["supplier_id"]).model_dump()
    if name == "get_budget_status":
        product_category = args["category"]
        return budget_service.get_status(db, product_category, "2026-09").model_dump()
    if name == "list_alternate_suppliers":
        alternates = supplier_service.list_alternates(db, args["sku"], args.get("exclude_supplier_id"))
        return {"alternates": [a.model_dump() for a in alternates]}
    if name == "propose_purchase_order":
        return {
            "action_type": "create_po",
            "product_sku": args["sku"],
            "supplier_id": args["supplier_id"],
            "qty": args["qty"],
            "rationale": args["rationale"],
        }
    if name == "propose_po_amendment":
        return {
            "action_type": "amend_po",
            "po_id": args["po_id"],
            "qty": args["new_qty"],
            "rationale": args["rationale"],
        }
    raise UnknownToolError(f"No such tool: {name}")
