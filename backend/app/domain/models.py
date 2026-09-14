from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel


class PurchaseOrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ProductOut(BaseModel):
    sku: str
    name: str
    category: str
    unit_cost: float

    model_config = {"from_attributes": True}


class InventorySnapshotOut(BaseModel):
    product_sku: str
    on_hand_qty: int
    storage_capacity_units: int
    storage_used_units: int

    model_config = {"from_attributes": True}

    @property
    def available_storage_units(self) -> int:
        return self.storage_capacity_units - self.storage_used_units


class DemandForecastOut(BaseModel):
    product_sku: str
    horizon_days: int
    forecast_qty: int
    recent_actual_sales_qty: int

    model_config = {"from_attributes": True}


class SupplierOut(BaseModel):
    id: int
    name: str
    product_sku: str
    lead_time_days: int
    min_order_qty: int
    reliability_score: float
    unit_price: float
    fulfillment_cap_qty: int | None = None

    model_config = {"from_attributes": True}


class PurchaseOrderOut(BaseModel):
    id: int
    product_sku: str
    supplier_id: int
    qty: int
    fulfilled_qty: int
    status: PurchaseOrderStatus
    created_at: datetime
    expected_arrival: datetime | None = None

    model_config = {"from_attributes": True}


class BudgetOut(BaseModel):
    category: str
    period: str
    available_amount: float

    model_config = {"from_attributes": True}


class ProposedAction(BaseModel):
    action_type: Literal["create_po", "amend_po", "no_action", "escalate"]
    product_sku: str | None = None
    supplier_id: int | None = None
    qty: int | None = None
    po_id: int | None = None


class AgentDecision(BaseModel):
    decision: Literal["accept", "modify", "reject", "investigate"]
    proposed_action: ProposedAction | None = None
    reasoning: str
    key_factors: list[str]
    confidence: float


class ValidatorVerdict(BaseModel):
    is_valid: bool
    violations: list[str] = []


class AgentRunOut(BaseModel):
    id: int
    scenario_type: str
    input_situation: dict[str, Any]
    tool_call_log: list[dict[str, Any]]
    decision: dict[str, Any] | None
    validator_verdict: dict[str, Any] | None
    human_action: str | None
    outcome: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
