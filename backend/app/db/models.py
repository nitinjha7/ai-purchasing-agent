from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    unit_cost: Mapped[float] = mapped_column(Float)


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    product_sku: Mapped[str] = mapped_column(ForeignKey("products.sku"), primary_key=True)
    on_hand_qty: Mapped[int] = mapped_column(Integer)
    storage_capacity_units: Mapped[int] = mapped_column(Integer)
    storage_used_units: Mapped[int] = mapped_column(Integer)


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"

    product_sku: Mapped[str] = mapped_column(ForeignKey("products.sku"), primary_key=True)
    horizon_days: Mapped[int] = mapped_column(Integer)
    forecast_qty: Mapped[int] = mapped_column(Integer)
    recent_actual_sales_qty: Mapped[int] = mapped_column(Integer)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    product_sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    lead_time_days: Mapped[int] = mapped_column(Integer)
    min_order_qty: Mapped[int] = mapped_column(Integer)
    reliability_score: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    # Mock ERP behavior: caps fulfillment at this qty when an order exceeds it (None = always fulfills in full)
    fulfillment_cap_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    qty: Mapped[int] = mapped_column(Integer)
    fulfilled_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expected_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    supplier: Mapped["Supplier"] = relationship()


class Budget(Base):
    __tablename__ = "budgets"

    category: Mapped[str] = mapped_column(String, primary_key=True)
    period: Mapped[str] = mapped_column(String, primary_key=True)
    available_amount: Mapped[float] = mapped_column(Float)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_type: Mapped[str] = mapped_column(String)
    input_situation: Mapped[dict] = mapped_column(JSON)
    tool_call_log: Mapped[list] = mapped_column(JSON, default=list)
    decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validator_verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    human_action: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
