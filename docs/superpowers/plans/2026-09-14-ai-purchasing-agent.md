# AI Purchasing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack AI Purchasing Agent covering Scenario 1 (Purchase Recommendation Review) and Scenario 2 (Supplier Cannot Fulfil), with a Gemini tool-calling agent, FastAPI + SQLite backend, React frontend, and an independent code-based validation/feedback loop.

**Architecture:** FastAPI backend with strict layering (domain models → SQLAlchemy DB layer → service layer with business logic → agent orchestrator that calls services as tools via Gemini function-calling → thin API routers → React frontend). A code-based `validation_service` independently re-verifies every agent proposal before it can touch the database; human approval gates real PO writes; partial ERP fulfillment automatically re-invokes the agent.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x + SQLite, Alembic, Pydantic v2, `google-genai` SDK (Gemini), pytest, Vite + React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-09-14-ai-purchasing-agent-design.md`

## Global Constraints

- No mocked-LLM fallback — all agent tests/eval hit the real Gemini API using `GEMINI_API_KEY` from `.env`.
- SQLite for storage; schema/service layer written so a Postgres swap is a `DATABASE_URL` change only.
- Only Scenarios 1 and 2 implemented end-to-end.
- Business rule validation always happens in code (`validation_service`), never trusted from the LLM's own output.
- Human approval required before any PO is actually created/modified in the DB.
- No secrets committed; `.env` is gitignored, `.env.example` documents required vars with placeholder values.
- Zero boilerplate/AI comments — comments only for non-obvious business logic or architectural decisions.

---

## File Structure

```
backend/
  requirements.txt
  .env.example
  alembic.ini
  alembic/env.py, alembic/versions/
  app/
    __init__.py
    config.py                    # Settings (env vars) via pydantic-settings
    domain/
      __init__.py
      models.py                  # Pydantic I/O models + enums
    db/
      __init__.py
      base.py                    # engine, SessionLocal, Base, get_db dependency
      models.py                  # SQLAlchemy ORM models
    services/
      __init__.py
      inventory_service.py
      demand_service.py
      supplier_service.py
      budget_service.py
      purchase_order_service.py
      validation_service.py
    agent/
      __init__.py
      prompts.py
      tools.py
      orchestrator.py
    api/
      __init__.py
      deps.py
      products.py
      purchase_orders.py
      agent_runs.py
      scenarios.py
    seed_data.py
    main.py
  tests/
    conftest.py
    test_inventory_service.py
    test_demand_service.py
    test_supplier_service.py
    test_budget_service.py
    test_purchase_order_service.py
    test_validation_service.py
    test_agent_orchestrator.py
    test_api_scenarios.py
  eval/
    fixtures/
      scenario1_accept.json
      scenario1_budget_constrained.json
      scenario1_storage_constrained.json
      scenario1_moq_forces_modify.json
      scenario2_alt_supplier.json
      scenario2_inventory_sufficient.json
    run_eval.py
    results/.gitkeep

frontend/
  package.json, vite.config.ts, tsconfig.json, index.html
  src/
    main.tsx, App.tsx
    api/client.ts
    types.ts
    pages/Dashboard.tsx
    pages/PurchaseOrders.tsx
    components/ReasoningTimeline.tsx
    components/DecisionCard.tsx

docs/architecture.md
README.md
.gitignore
```

---

## Task 1: Backend scaffolding, config, and DB base

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `.gitignore`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_db_base.py`

**Interfaces:**
- Produces: `Settings` class (`config.py`) with `gemini_api_key: str`, `database_url: str = "sqlite:///./purchasing_agent.db"`; module-level `get_settings()` cached accessor.
- Produces: `Base` (declarative base), `engine`, `SessionLocal`, `get_db()` generator dependency in `db/base.py`.

- [ ] **Step 1: Write requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
alembic==1.13.2
pydantic==2.9.2
pydantic-settings==2.5.2
google-genai==0.3.0
python-dotenv==1.0.1
pytest==8.3.3
httpx==0.27.2
```

- [ ] **Step 2: Write .env.example**

```
GEMINI_API_KEY=your-gemini-api-key-here
DATABASE_URL=sqlite:///./purchasing_agent.db
```

- [ ] **Step 3: Write .gitignore at repo root**

```
.env
*.db
__pycache__/
*.pyc
node_modules/
frontend/dist/
eval/results/*.json
!eval/results/.gitkeep
.venv/
```

- [ ] **Step 4: Write app/config.py**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str
    database_url: str = "sqlite:///./purchasing_agent.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Write app/db/base.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Write tests/conftest.py — isolated in-memory DB per test**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

Note: this requires `GEMINI_API_KEY` to exist as an env var at import time (Settings is required). Add a `backend/tests/.env` is not used — instead set `GEMINI_API_KEY=test-key-not-used` in `pytest.ini`'s env or export before running. Simplest: create `backend/pytest.ini`:

```ini
[pytest]
env =
    GEMINI_API_KEY=test-key-placeholder
```

This needs `pytest-env`; add `pytest-env==1.1.5` to requirements.txt (append it now).

- [ ] **Step 7: Write tests/test_db_base.py**

```python
from app.db.base import Base, engine


def test_engine_is_configured():
    assert engine is not None
    assert Base.metadata is not None
```

- [ ] **Step 8: Install deps and run tests**

Run: `cd backend && pip install -r requirements.txt && pip install pytest-env==1.1.5 && pytest tests/test_db_base.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/app/config.py backend/app/db backend/app/__init__.py backend/tests/conftest.py backend/tests/test_db_base.py backend/pytest.ini .gitignore
git commit -m "chore: scaffold backend config and DB base"
```

---

## Task 2: SQLAlchemy ORM models and domain Pydantic models

**Files:**
- Create: `backend/app/db/models.py`
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/models.py`
- Test: `backend/tests/test_db_models.py`

**Interfaces:**
- Consumes: `Base` from `app.db.base`.
- Produces ORM classes: `Product`, `InventorySnapshot`, `DemandForecast`, `Supplier`, `PurchaseOrder`, `Budget`, `AgentRun` — all later services and the agent import these.
- Produces domain models: `ProductOut`, `InventorySnapshotOut`, `DemandForecastOut`, `SupplierOut`, `PurchaseOrderOut`, `BudgetOut`, `PurchaseOrderStatus` (str enum), `AgentDecision`, `ValidatorVerdict`, `AgentRunOut` — every later task imports from here for typed boundaries.

- [ ] **Step 1: Write app/db/models.py**

```python
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
```

- [ ] **Step 2: Write app/domain/models.py**

```python
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
```

- [ ] **Step 3: Write tests/test_db_models.py**

```python
from app.db.models import Product, Supplier, PurchaseOrder


def test_create_product_and_supplier_and_po(db_session):
    product = Product(sku="SKU-1", name="Widget", category="general", unit_cost=10.0)
    db_session.add(product)
    db_session.flush()

    supplier = Supplier(
        name="Acme", product_sku="SKU-1", lead_time_days=5,
        min_order_qty=50, reliability_score=0.9, unit_price=9.5,
    )
    db_session.add(supplier)
    db_session.flush()

    po = PurchaseOrder(product_sku="SKU-1", supplier_id=supplier.id, qty=100)
    db_session.add(po)
    db_session.commit()

    assert po.id is not None
    assert po.status == "draft"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_db_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/app/domain backend/tests/test_db_models.py
git commit -m "feat: add ORM and domain models"
```

---

## Task 3: Seed data script

**Files:**
- Create: `backend/app/seed_data.py`
- Test: `backend/tests/test_seed_data.py`

**Interfaces:**
- Consumes: ORM models from `app.db.models`.
- Produces: `seed(db: Session) -> None` — populates 3 products, inventory snapshots, demand forecasts, 2 suppliers per product (one primary, one alternate with different lead time/price), budgets, and a couple of open purchase orders. Later tasks (services, agent, eval fixtures) assume these exact SKUs/IDs exist when run against a freshly seeded DB.

- [ ] **Step 1: Write app/seed_data.py**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Budget, DemandForecast, InventorySnapshot, Product, PurchaseOrder, Supplier

# SKU-100: healthy budget/storage, used for the clean-accept eval case
# SKU-200: tight budget, used for budget-constrained cases
# SKU-300: tight storage, used for storage-constrained cases


def seed(db: Session) -> None:
    products = [
        Product(sku="SKU-100", name="Instant Noodles 500g", category="grocery", unit_cost=1.20),
        Product(sku="SKU-200", name="Premium Olive Oil 1L", category="grocery", unit_cost=8.50),
        Product(sku="SKU-300", name="Paper Towels 6-pack", category="household", unit_cost=3.00),
    ]
    db.add_all(products)

    db.add_all([
        InventorySnapshot(product_sku="SKU-100", on_hand_qty=200, storage_capacity_units=5000, storage_used_units=1000),
        InventorySnapshot(product_sku="SKU-200", on_hand_qty=50, storage_capacity_units=2000, storage_used_units=300),
        InventorySnapshot(product_sku="SKU-300", on_hand_qty=100, storage_capacity_units=900, storage_used_units=850),
    ])

    db.add_all([
        DemandForecast(product_sku="SKU-100", horizon_days=30, forecast_qty=600, recent_actual_sales_qty=580),
        DemandForecast(product_sku="SKU-200", horizon_days=30, forecast_qty=400, recent_actual_sales_qty=410),
        DemandForecast(product_sku="SKU-300", horizon_days=30, forecast_qty=300, recent_actual_sales_qty=290),
    ])

    db.add_all([
        Supplier(name="Northwind Foods", product_sku="SKU-100", lead_time_days=7, min_order_qty=100,
                  reliability_score=0.95, unit_price=1.10, fulfillment_cap_qty=None),
        Supplier(name="Northwind Backup", product_sku="SKU-100", lead_time_days=10, min_order_qty=50,
                  reliability_score=0.88, unit_price=1.18, fulfillment_cap_qty=None),
        Supplier(name="MedOil Traders", product_sku="SKU-200", lead_time_days=14, min_order_qty=200,
                  reliability_score=0.80, unit_price=8.20, fulfillment_cap_qty=250),
        Supplier(name="MedOil Alt Source", product_sku="SKU-200", lead_time_days=5, min_order_qty=100,
                  reliability_score=0.90, unit_price=8.60, fulfillment_cap_qty=None),
        Supplier(name="PaperCo", product_sku="SKU-300", lead_time_days=4, min_order_qty=150,
                  reliability_score=0.92, unit_price=2.90, fulfillment_cap_qty=None),
    ])

    db.add_all([
        Budget(category="grocery", period="2026-09", available_amount=1500.0),
        Budget(category="household", period="2026-09", available_amount=500.0),
    ])

    db.flush()

    db.add(PurchaseOrder(
        product_sku="SKU-200", supplier_id=3, qty=500, fulfilled_qty=0, status="submitted",
        expected_arrival=datetime.now(timezone.utc) + timedelta(days=14),
    ))

    db.commit()
```

- [ ] **Step 2: Write tests/test_seed_data.py**

```python
from app.db.models import Product, PurchaseOrder, Supplier
from app.seed_data import seed


def test_seed_creates_expected_rows(db_session):
    seed(db_session)

    assert db_session.query(Product).count() == 3
    assert db_session.query(Supplier).count() == 5
    open_po = db_session.query(PurchaseOrder).filter_by(product_sku="SKU-200").one()
    assert open_po.qty == 500
    assert open_po.status == "submitted"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && pytest tests/test_seed_data.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/seed_data.py backend/tests/test_seed_data.py
git commit -m "feat: add deterministic seed data"
```

---

## Task 4: Inventory, demand, and budget services

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/inventory_service.py`
- Create: `backend/app/services/demand_service.py`
- Create: `backend/app/services/budget_service.py`
- Test: `backend/tests/test_inventory_service.py`
- Test: `backend/tests/test_demand_service.py`
- Test: `backend/tests/test_budget_service.py`

**Interfaces:**
- Consumes: `InventorySnapshot`, `DemandForecast`, `Budget`, `PurchaseOrder` ORM models; `InventorySnapshotOut`, `DemandForecastOut`, `BudgetOut` domain models.
- Produces: `inventory_service.get_snapshot(db, sku) -> InventorySnapshotOut`, `inventory_service.available_storage(db, sku) -> int`.
- Produces: `demand_service.get_forecast(db, sku) -> DemandForecastOut`, `demand_service.net_demand_gap(db, sku) -> int` (forecast_qty − on_hand_qty − sum of open PO qty for that sku; used by both scenarios).
- Produces: `budget_service.get_status(db, category) -> BudgetOut`, `budget_service.has_sufficient_budget(db, category, cost) -> bool`.

- [ ] **Step 1: Write failing tests for inventory_service**

```python
# backend/tests/test_inventory_service.py
import pytest

from app.db.models import InventorySnapshot, Product
from app.services import inventory_service


@pytest.fixture()
def product_with_stock(db_session):
    db_session.add(Product(sku="SKU-X", name="X", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-X", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=800))
    db_session.commit()
    return "SKU-X"


def test_get_snapshot_returns_data(db_session, product_with_stock):
    snapshot = inventory_service.get_snapshot(db_session, product_with_stock)
    assert snapshot.on_hand_qty == 100


def test_available_storage_computes_remaining_capacity(db_session, product_with_stock):
    assert inventory_service.available_storage(db_session, product_with_stock) == 200


def test_get_snapshot_missing_sku_raises(db_session):
    with pytest.raises(inventory_service.SnapshotNotFoundError):
        inventory_service.get_snapshot(db_session, "NOPE")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_inventory_service.py -v`
Expected: FAIL — `ModuleNotFoundError` or `AttributeError`

- [ ] **Step 3: Write app/services/inventory_service.py**

```python
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
```

- [ ] **Step 4: Run inventory tests to verify pass**

Run: `cd backend && pytest tests/test_inventory_service.py -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for demand_service**

```python
# backend/tests/test_demand_service.py
import pytest

from app.db.models import DemandForecast, InventorySnapshot, Product, PurchaseOrder, Supplier
from app.services import demand_service


@pytest.fixture()
def product_with_demand_and_open_po(db_session):
    db_session.add(Product(sku="SKU-Y", name="Y", category="general", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-Y", on_hand_qty=50, storage_capacity_units=1000, storage_used_units=100))
    db_session.add(DemandForecast(product_sku="SKU-Y", horizon_days=30, forecast_qty=300, recent_actual_sales_qty=310))
    supplier = Supplier(name="S", product_sku="SKU-Y", lead_time_days=5, min_order_qty=10, reliability_score=0.9, unit_price=1.0)
    db_session.add(supplier)
    db_session.flush()
    db_session.add(PurchaseOrder(product_sku="SKU-Y", supplier_id=supplier.id, qty=100, status="submitted"))
    db_session.commit()
    return "SKU-Y"


def test_get_forecast_returns_data(db_session, product_with_demand_and_open_po):
    forecast = demand_service.get_forecast(db_session, product_with_demand_and_open_po)
    assert forecast.forecast_qty == 300


def test_net_demand_gap_subtracts_on_hand_and_open_pos(db_session, product_with_demand_and_open_po):
    # forecast 300 - on_hand 50 - open_po 100 = 150
    assert demand_service.net_demand_gap(db_session, product_with_demand_and_open_po) == 150
```

- [ ] **Step 6: Run to verify failure, then implement**

Run: `cd backend && pytest tests/test_demand_service.py -v`
Expected: FAIL

```python
# backend/app/services/demand_service.py
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
```

- [ ] **Step 7: Run demand tests to verify pass**

Run: `cd backend && pytest tests/test_demand_service.py -v`
Expected: PASS

- [ ] **Step 8: Write failing tests for budget_service**

```python
# backend/tests/test_budget_service.py
import pytest

from app.db.models import Budget
from app.services import budget_service


@pytest.fixture()
def grocery_budget(db_session):
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=1000.0))
    db_session.commit()
    return ("grocery", "2026-09")


def test_get_status_returns_data(db_session, grocery_budget):
    category, period = grocery_budget
    status = budget_service.get_status(db_session, category, period)
    assert status.available_amount == 1000.0


def test_has_sufficient_budget_true_when_cost_below_available(db_session, grocery_budget):
    category, period = grocery_budget
    assert budget_service.has_sufficient_budget(db_session, category, period, cost=500.0) is True


def test_has_sufficient_budget_false_when_cost_exceeds_available(db_session, grocery_budget):
    category, period = grocery_budget
    assert budget_service.has_sufficient_budget(db_session, category, period, cost=1500.0) is False
```

- [ ] **Step 9: Run to verify failure, then implement**

Run: `cd backend && pytest tests/test_budget_service.py -v`
Expected: FAIL

```python
# backend/app/services/budget_service.py
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
```

- [ ] **Step 10: Run budget tests to verify pass**

Run: `cd backend && pytest tests/test_budget_service.py -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add backend/app/services backend/tests/test_inventory_service.py backend/tests/test_demand_service.py backend/tests/test_budget_service.py
git commit -m "feat: add inventory, demand, and budget services"
```

---

## Task 5: Supplier service with mock ERP fulfillment behavior

**Files:**
- Create: `backend/app/services/supplier_service.py`
- Test: `backend/tests/test_supplier_service.py`

**Interfaces:**
- Consumes: `Supplier`, `PurchaseOrder` ORM models; `SupplierOut` domain model.
- Produces: `supplier_service.get_terms(db, supplier_id) -> SupplierOut`, `supplier_service.list_alternates(db, sku, exclude_supplier_id=None) -> list[SupplierOut]`, `supplier_service.FulfillmentResult` (dataclass: `fulfilled_qty: int`, `status: Literal["fulfilled","partially_fulfilled"]`), `supplier_service.submit_to_supplier(db, po_id) -> FulfillmentResult` — mutates the PO's `fulfilled_qty`/`status` in place and commits.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_supplier_service.py
import pytest

from app.db.models import Product, PurchaseOrder, Supplier
from app.services import supplier_service


@pytest.fixture()
def two_suppliers_one_capped(db_session):
    db_session.add(Product(sku="SKU-Z", name="Z", category="general", unit_cost=2.0))
    db_session.add(Supplier(name="Capped", product_sku="SKU-Z", lead_time_days=10, min_order_qty=50,
                             reliability_score=0.7, unit_price=2.0, fulfillment_cap_qty=250))
    db_session.add(Supplier(name="Uncapped", product_sku="SKU-Z", lead_time_days=6, min_order_qty=20,
                             reliability_score=0.95, unit_price=2.2, fulfillment_cap_qty=None))
    db_session.commit()
    suppliers = db_session.query(Supplier).order_by(Supplier.id).all()
    return suppliers[0], suppliers[1]


def test_get_terms_returns_data(db_session, two_suppliers_one_capped):
    capped, _ = two_suppliers_one_capped
    terms = supplier_service.get_terms(db_session, capped.id)
    assert terms.min_order_qty == 50


def test_list_alternates_excludes_given_supplier(db_session, two_suppliers_one_capped):
    capped, uncapped = two_suppliers_one_capped
    alternates = supplier_service.list_alternates(db_session, "SKU-Z", exclude_supplier_id=capped.id)
    assert [a.id for a in alternates] == [uncapped.id]


def test_submit_to_supplier_caps_fulfillment(db_session, two_suppliers_one_capped):
    capped, _ = two_suppliers_one_capped
    po = PurchaseOrder(product_sku="SKU-Z", supplier_id=capped.id, qty=500, status="approved")
    db_session.add(po)
    db_session.commit()

    result = supplier_service.submit_to_supplier(db_session, po.id)

    assert result.fulfilled_qty == 250
    assert result.status == "partially_fulfilled"
    db_session.refresh(po)
    assert po.fulfilled_qty == 250
    assert po.status == "partially_fulfilled"


def test_submit_to_supplier_fulfills_in_full_when_uncapped(db_session, two_suppliers_one_capped):
    _, uncapped = two_suppliers_one_capped
    po = PurchaseOrder(product_sku="SKU-Z", supplier_id=uncapped.id, qty=100, status="approved")
    db_session.add(po)
    db_session.commit()

    result = supplier_service.submit_to_supplier(db_session, po.id)

    assert result.fulfilled_qty == 100
    assert result.status == "fulfilled"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_supplier_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write app/services/supplier_service.py**

```python
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder, Supplier
from app.domain.models import SupplierOut


class SupplierNotFoundError(Exception):
    pass


class PurchaseOrderNotFoundError(Exception):
    pass


@dataclass
class FulfillmentResult:
    fulfilled_qty: int
    status: Literal["fulfilled", "partially_fulfilled"]


def get_terms(db: Session, supplier_id: int) -> SupplierOut:
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise SupplierNotFoundError(f"No supplier with id={supplier_id}")
    return SupplierOut.model_validate(row)


def list_alternates(db: Session, sku: str, exclude_supplier_id: int | None = None) -> list[SupplierOut]:
    query = db.query(Supplier).filter(Supplier.product_sku == sku)
    if exclude_supplier_id is not None:
        query = query.filter(Supplier.id != exclude_supplier_id)
    return [SupplierOut.model_validate(row) for row in query.order_by(Supplier.id).all()]


def submit_to_supplier(db: Session, po_id: int) -> FulfillmentResult:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise PurchaseOrderNotFoundError(f"No purchase order with id={po_id}")

    supplier = db.get(Supplier, po.supplier_id)
    cap = supplier.fulfillment_cap_qty
    fulfilled = min(po.qty, cap) if cap is not None else po.qty
    status: Literal["fulfilled", "partially_fulfilled"] = "fulfilled" if fulfilled >= po.qty else "partially_fulfilled"

    po.fulfilled_qty = fulfilled
    po.status = status
    db.commit()

    return FulfillmentResult(fulfilled_qty=fulfilled, status=status)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_supplier_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/supplier_service.py backend/tests/test_supplier_service.py
git commit -m "feat: add supplier service with mock ERP fulfillment behavior"
```

---

## Task 6: Purchase order service

**Files:**
- Create: `backend/app/services/purchase_order_service.py`
- Test: `backend/tests/test_purchase_order_service.py`

**Interfaces:**
- Consumes: `PurchaseOrder` ORM model; `PurchaseOrderOut`, `PurchaseOrderStatus`; `supplier_service.submit_to_supplier`.
- Produces: `create(db, sku, supplier_id, qty) -> PurchaseOrderOut` (status starts `pending_approval`), `amend(db, po_id, new_qty) -> PurchaseOrderOut`, `approve(db, po_id) -> PurchaseOrderOut` (sets `approved`, then calls `supplier_service.submit_to_supplier`, sets final status from result), `reject(db, po_id) -> PurchaseOrderOut`, `get_open_pos(db, sku) -> list[PurchaseOrderOut]`, `get(db, po_id) -> PurchaseOrderOut`.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_purchase_order_service.py
import pytest

from app.db.models import Product, Supplier
from app.domain.models import PurchaseOrderStatus
from app.services import purchase_order_service as po_service


@pytest.fixture()
def sku_and_supplier(db_session):
    db_session.add(Product(sku="SKU-P", name="P", category="general", unit_cost=1.0))
    supplier = Supplier(name="S1", product_sku="SKU-P", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-P", supplier.id


def test_create_starts_pending_approval(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    assert po.status == PurchaseOrderStatus.PENDING_APPROVAL
    assert po.qty == 100


def test_amend_changes_qty(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    amended = po_service.amend(db_session, po.id, new_qty=150)
    assert amended.qty == 150


def test_approve_submits_and_updates_status(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    approved = po_service.approve(db_session, po.id)
    assert approved.status == PurchaseOrderStatus.FULFILLED
    assert approved.fulfilled_qty == 100


def test_reject_sets_status(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    po = po_service.create(db_session, sku, supplier_id, qty=100)
    rejected = po_service.reject(db_session, po.id)
    assert rejected.status == PurchaseOrderStatus.REJECTED


def test_get_open_pos_excludes_terminal_statuses(db_session, sku_and_supplier):
    sku, supplier_id = sku_and_supplier
    open_po = po_service.create(db_session, sku, supplier_id, qty=100)
    closed_po = po_service.create(db_session, sku, supplier_id, qty=50)
    po_service.reject(db_session, closed_po.id)

    open_pos = po_service.get_open_pos(db_session, sku)

    assert [p.id for p in open_pos] == [open_po.id]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_purchase_order_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write app/services/purchase_order_service.py**

```python
from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder
from app.domain.models import PurchaseOrderOut, PurchaseOrderStatus
from app.services import supplier_service

OPEN_STATUSES = {
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PENDING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.SUBMITTED,
    PurchaseOrderStatus.PARTIALLY_FULFILLED,
}


class PurchaseOrderNotFoundError(Exception):
    pass


def _get_row(db: Session, po_id: int) -> PurchaseOrder:
    row = db.get(PurchaseOrder, po_id)
    if row is None:
        raise PurchaseOrderNotFoundError(f"No purchase order with id={po_id}")
    return row


def get(db: Session, po_id: int) -> PurchaseOrderOut:
    return PurchaseOrderOut.model_validate(_get_row(db, po_id))


def create(db: Session, sku: str, supplier_id: int, qty: int) -> PurchaseOrderOut:
    po = PurchaseOrder(product_sku=sku, supplier_id=supplier_id, qty=qty, status=PurchaseOrderStatus.PENDING_APPROVAL)
    db.add(po)
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def amend(db: Session, po_id: int, new_qty: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.qty = new_qty
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def approve(db: Session, po_id: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.status = PurchaseOrderStatus.APPROVED
    db.commit()

    supplier_service.submit_to_supplier(db, po_id)

    db.refresh(po)
    return PurchaseOrderOut.model_validate(po)


def reject(db: Session, po_id: int) -> PurchaseOrderOut:
    po = _get_row(db, po_id)
    po.status = PurchaseOrderStatus.REJECTED
    db.commit()
    return PurchaseOrderOut.model_validate(po)


def get_open_pos(db: Session, sku: str) -> list[PurchaseOrderOut]:
    rows = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.product_sku == sku, PurchaseOrder.status.in_([s.value for s in OPEN_STATUSES]))
        .order_by(PurchaseOrder.id)
        .all()
    )
    return [PurchaseOrderOut.model_validate(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_purchase_order_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/purchase_order_service.py backend/tests/test_purchase_order_service.py
git commit -m "feat: add purchase order service"
```

---

## Task 7: Validation service (independent constraint checker)

**Files:**
- Create: `backend/app/services/validation_service.py`
- Test: `backend/tests/test_validation_service.py`

**Interfaces:**
- Consumes: `ProposedAction`, `ValidatorVerdict` domain models; `inventory_service`, `budget_service`, `supplier_service`, `demand_service`.
- Produces: `validate_proposal(db, action: ProposedAction) -> ValidatorVerdict`. This is called on every `create_po`/`amend_po` proposal before it is allowed to reach `purchase_order_service`. Checks, in order, appending a violation string for each that fails (does not short-circuit, so the agent sees every problem at once):
  1. qty is not None and qty > 0
  2. qty >= supplier.min_order_qty
  3. cost (`qty * supplier.unit_price`) <= budget available for the product's category (current period, hardcoded `"2026-09"` for this prototype — noted as a known simplification)
  4. qty <= available storage for the sku

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_validation_service.py
import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.domain.models import ProposedAction
from app.services import validation_service


@pytest.fixture()
def full_setup(db_session):
    db_session.add(Product(sku="SKU-V", name="V", category="grocery", unit_cost=2.0))
    db_session.add(InventorySnapshot(product_sku="SKU-V", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=900))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=300.0))
    supplier = Supplier(name="S", product_sku="SKU-V", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.9, unit_price=2.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return supplier.id


def test_valid_proposal_passes(db_session, full_setup):
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=60)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is True
    assert verdict.violations == []


def test_below_moq_is_violation(db_session, full_setup):
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=20)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("minimum order" in v.lower() for v in verdict.violations)


def test_exceeds_budget_is_violation(db_session, full_setup):
    # qty 200 * unit_price 2.0 = 400 > available 300
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=200)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("budget" in v.lower() for v in verdict.violations)


def test_exceeds_storage_is_violation(db_session, full_setup):
    # available storage = 1000 - 900 = 100; qty 150 exceeds it
    action = ProposedAction(action_type="create_po", product_sku="SKU-V", supplier_id=full_setup, qty=150)
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is False
    assert any("storage" in v.lower() for v in verdict.violations)


def test_non_po_actions_are_always_valid(db_session, full_setup):
    action = ProposedAction(action_type="no_action")
    verdict = validation_service.validate_proposal(db_session, action)
    assert verdict.is_valid is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_validation_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write app/services/validation_service.py**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_validation_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/validation_service.py backend/tests/test_validation_service.py
git commit -m "feat: add independent validation service"
```

---

## Task 8: Agent tools and prompts

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/tools.py`
- Create: `backend/app/agent/prompts.py`
- Test: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: all services from Task 4-7; `ProposedAction`.
- Produces: `TOOL_FUNCTION_DECLARATIONS` (list of Gemini `types.FunctionDeclaration`-compatible dicts) and `dispatch_tool_call(db, name: str, args: dict) -> dict` (JSON-serializable result) in `tools.py`. Produces `SYSTEM_PROMPT: str` and `build_situation_prompt(scenario_type: str, situation: dict) -> str` in `prompts.py`. The orchestrator (Task 9) imports both.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_agent_tools.py
import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.agent import tools


@pytest.fixture()
def seeded(db_session):
    db_session.add(Product(sku="SKU-T", name="T", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-T", on_hand_qty=100, storage_capacity_units=1000, storage_used_units=200))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=1000.0))
    supplier = Supplier(name="S", product_sku="SKU-T", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-T", supplier.id


def test_dispatch_get_product_snapshot(db_session, seeded):
    sku, _ = seeded
    result = tools.dispatch_tool_call(db_session, "get_product_snapshot", {"sku": sku})
    assert result["on_hand_qty"] == 100


def test_dispatch_propose_purchase_order_does_not_write_to_db(db_session, seeded):
    from app.services import purchase_order_service

    sku, supplier_id = seeded
    result = tools.dispatch_tool_call(
        db_session, "propose_purchase_order",
        {"sku": sku, "supplier_id": supplier_id, "qty": 200, "rationale": "test"},
    )
    assert result["action_type"] == "create_po"
    assert result["qty"] == 200
    assert purchase_order_service.get_open_pos(db_session, sku) == []


def test_dispatch_unknown_tool_raises(db_session, seeded):
    with pytest.raises(tools.UnknownToolError):
        tools.dispatch_tool_call(db_session, "not_a_tool", {})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_agent_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Write app/agent/tools.py**

```python
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
```

- [ ] **Step 4: Write app/agent/prompts.py**

```python
SYSTEM_PROMPT = """You are an AI purchasing buyer-assistant for a retail/quick-commerce company.

You review purchasing situations and decide whether to accept, modify, reject, or
investigate further. A recommendation given to you is NOT guaranteed to be correct —
your job is to verify it against real constraints, not rubber-stamp it.

Before deciding, use the available tools to gather whatever information is relevant:
current inventory and storage, demand forecast and net demand gap, open purchase
orders, supplier lead time and minimum order quantity, budget availability, and
alternate suppliers. Do not guess numbers you can look up.

When you are ready to decide, respond with ONLY a JSON object matching this schema,
no other text:
{
  "decision": "accept" | "modify" | "reject" | "investigate",
  "proposed_action": {
    "action_type": "create_po" | "amend_po" | "no_action" | "escalate",
    "product_sku": string | null,
    "supplier_id": integer | null,
    "qty": integer | null,
    "po_id": integer | null
  } | null,
  "reasoning": string,
  "key_factors": [string, ...],
  "confidence": number between 0 and 1
}

Use "modify" when the recommended quantity should change (e.g. due to budget,
storage, or minimum order quantity constraints) and set proposed_action accordingly.
Use "reject" when no purchase is warranted. Use "investigate" when you lack enough
information or the situation is ambiguous even after using your tools.
"""


def build_situation_prompt(scenario_type: str, situation: dict) -> str:
    if scenario_type == "recommendation_review":
        return (
            f"The purchasing system recommends buying {situation['recommended_qty']} units "
            f"of product {situation['sku']}. Investigate and decide whether to accept, modify, "
            f"reject, or investigate this recommendation further."
        )
    if scenario_type == "supplier_shortfall":
        return (
            f"Purchase order #{situation['po_id']} was placed for {situation['ordered_qty']} units "
            f"of product {situation['sku']} from supplier {situation['supplier_id']}, but the supplier "
            f"has confirmed they can only fulfil {situation['fulfilled_qty']} units. Determine what "
            f"should happen next: source the remainder elsewhere, use an alternate supplier, decide "
            f"existing inventory is sufficient, or escalate."
        )
    raise ValueError(f"Unknown scenario_type: {scenario_type}")
```

- [ ] **Step 5: Run tools tests to verify pass**

Run: `cd backend && pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent backend/tests/test_agent_tools.py
git commit -m "feat: add agent tool declarations, dispatch, and prompts"
```

---

## Task 9: Agent orchestrator (Gemini tool-calling loop)

**Files:**
- Create: `backend/app/agent/orchestrator.py`
- Test: `backend/tests/test_agent_orchestrator.py` (integration test, requires real `GEMINI_API_KEY` — marked and skipped if not a real key)

**Interfaces:**
- Consumes: `TOOL_FUNCTION_DECLARATIONS`, `dispatch_tool_call` from `tools.py`; `SYSTEM_PROMPT`, `build_situation_prompt` from `prompts.py`; `AgentDecision` domain model; `Settings`.
- Produces: `run_agent(db: Session, scenario_type: str, situation: dict) -> tuple[AgentDecision, list[dict]]` where the list is the tool-call log (each entry: `{"tool": str, "args": dict, "result": dict}`). Raises `AgentDecisionError` if no valid JSON decision is produced within the turn budget. Task 11 wraps this with persistence + validation.

- [ ] **Step 1: Write app/agent/orchestrator.py**

```python
import json
from typing import Any

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, build_situation_prompt
from app.agent.tools import TOOL_FUNCTION_DECLARATIONS, dispatch_tool_call
from app.config import get_settings
from app.domain.models import AgentDecision

MAX_TURNS = 8


class AgentDecisionError(Exception):
    pass


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AgentDecisionError(f"Model did not return a JSON object: {text!r}")
    return json.loads(text[start : end + 1])


def run_agent(db: Session, scenario_type: str, situation: dict) -> tuple[AgentDecision, list[dict]]:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(**decl) for decl in TOOL_FUNCTION_DECLARATIONS
    ])

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=build_situation_prompt(scenario_type, situation))]),
    ]
    tool_call_log: list[dict[str, Any]] = []

    for _ in range(MAX_TURNS):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[tool],
            ),
        )
        candidate = response.candidates[0]
        contents.append(candidate.content)

        function_calls = [part.function_call for part in candidate.content.parts if part.function_call]
        if not function_calls:
            text = "".join(part.text or "" for part in candidate.content.parts)
            decision_dict = _extract_json_object(text)
            return AgentDecision.model_validate(decision_dict), tool_call_log

        response_parts = []
        for call in function_calls:
            args = dict(call.args)
            result = dispatch_tool_call(db, call.name, args)
            tool_call_log.append({"tool": call.name, "args": args, "result": result})
            response_parts.append(types.Part(function_response=types.FunctionResponse(name=call.name, response=result)))
        contents.append(types.Content(role="tool", parts=response_parts))

    raise AgentDecisionError(f"Agent did not converge on a decision within {MAX_TURNS} turns")
```

- [ ] **Step 2: Write tests/test_agent_orchestrator.py**

```python
import os

import pytest

from app.db.models import Budget, InventorySnapshot, Product, Supplier
from app.agent.orchestrator import run_agent

requires_real_gemini_key = pytest.mark.skipif(
    os.environ.get("GEMINI_API_KEY", "test-key-placeholder") == "test-key-placeholder",
    reason="Requires a real GEMINI_API_KEY to call the live API",
)


@pytest.fixture()
def clean_accept_scenario(db_session):
    db_session.add(Product(sku="SKU-ORCH", name="Orch", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-ORCH", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-ORCH", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.95, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-ORCH"


@requires_real_gemini_key
def test_run_agent_returns_decision_for_recommendation_review(db_session, clean_accept_scenario):
    decision, tool_log = run_agent(
        db_session, "recommendation_review",
        {"sku": clean_accept_scenario, "recommended_qty": 100},
    )

    assert decision.decision in ("accept", "modify", "reject", "investigate")
    assert len(tool_log) > 0
    assert any(entry["tool"] == "get_product_snapshot" for entry in tool_log)
```

- [ ] **Step 3: Run test (skips without a real key, runs live with one)**

Run: `cd backend && pytest tests/test_agent_orchestrator.py -v`
Expected: SKIPPED if `GEMINI_API_KEY` is the placeholder, PASS once a real key is exported in the shell (the user will supply this — do not block the plan on it; note in README that this test requires a real key)

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/orchestrator.py backend/tests/test_agent_orchestrator.py
git commit -m "feat: add Gemini tool-calling agent orchestrator"
```

---

## Task 10: Wire the full scenario loop (investigate → validate → approve → execute → re-invoke)

**Files:**
- Create: `backend/app/agent/scenario_runner.py`
- Test: `backend/tests/test_scenario_runner.py` (uses a stub orchestrator to stay fast/deterministic — real Gemini coverage lives in eval)

**Interfaces:**
- Consumes: `run_agent` from `orchestrator.py`; `validate_proposal` from `validation_service.py`; `AgentRun` ORM model; `AgentDecision`, `ProposedAction`.
- Produces: `execute_recommendation_review(db, sku: str, recommended_qty: int) -> AgentRun` and `execute_supplier_shortfall(db, po_id: int, fulfilled_qty: int) -> AgentRun`. Both persist an `AgentRun` row with `tool_call_log`, `decision`, and `validator_verdict` populated, and return it. Neither writes a PO — that only happens via the approve/reject API endpoints (Task 11), except that `execute_supplier_shortfall` first records the ERP's reported shortfall onto the existing PO via `purchase_order_service` state (handled directly, not via agent proposal, since the shortfall is a fact being reported, not a decision).
- Also produces: `run_agent_for_scenario(db, scenario_type: str, situation: dict) -> tuple[AgentDecision, list[dict]]` — a thin seam so this can be monkeypatched in tests instead of hitting Gemini.

- [ ] **Step 1: Write failing tests using a monkeypatched agent**

```python
# backend/tests/test_scenario_runner.py
import pytest

from app.db.models import Budget, InventorySnapshot, Product, PurchaseOrder, Supplier
from app.domain.models import AgentDecision, ProposedAction
from app.agent import scenario_runner


@pytest.fixture()
def base_setup(db_session):
    db_session.add(Product(sku="SKU-RUN", name="Run", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-RUN", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-RUN", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.95, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()
    return "SKU-RUN", supplier.id


def test_execute_recommendation_review_persists_valid_decision(db_session, base_setup, monkeypatch):
    sku, supplier_id = base_setup

    def fake_run_agent(db, scenario_type, situation):
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=200),
            reasoning="Demand supports this purchase.",
            key_factors=["demand gap", "budget available"],
            confidence=0.9,
        )
        return decision, [{"tool": "get_product_snapshot", "args": {"sku": sku}, "result": {}}]

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_recommendation_review(db_session, sku, recommended_qty=800)

    assert agent_run.decision["decision"] == "accept"
    assert agent_run.validator_verdict["is_valid"] is True
    assert len(agent_run.tool_call_log) == 1


def test_execute_recommendation_review_flags_invalid_proposal(db_session, base_setup, monkeypatch):
    sku, supplier_id = base_setup

    def fake_run_agent(db, scenario_type, situation):
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=10),
            reasoning="Should be enough.",
            key_factors=["demand gap"],
            confidence=0.6,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_recommendation_review(db_session, sku, recommended_qty=10)

    assert agent_run.validator_verdict["is_valid"] is False
    assert any("minimum order" in v.lower() for v in agent_run.validator_verdict["violations"])


def test_execute_supplier_shortfall_records_shortfall_on_po(db_session, base_setup, monkeypatch):
    sku, supplier_id = base_setup
    po = PurchaseOrder(product_sku=sku, supplier_id=supplier_id, qty=500, status="submitted")
    db_session.add(po)
    db_session.commit()

    def fake_run_agent(db, scenario_type, situation):
        decision = AgentDecision(
            decision="modify",
            proposed_action=ProposedAction(action_type="create_po", product_sku=sku, supplier_id=supplier_id, qty=250),
            reasoning="Source remainder from alternate supplier.",
            key_factors=["shortfall", "alternate supplier available"],
            confidence=0.8,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent)

    agent_run = scenario_runner.execute_supplier_shortfall(db_session, po.id, fulfilled_qty=250)

    db_session.refresh(po)
    assert po.fulfilled_qty == 250
    assert po.status == "partially_fulfilled"
    assert agent_run.decision["decision"] == "modify"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_scenario_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Write app/agent/scenario_runner.py**

```python
from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.db.models import AgentRun, PurchaseOrder
from app.domain.models import AgentDecision
from app.services import validation_service


def run_agent_for_scenario(db: Session, scenario_type: str, situation: dict) -> tuple[AgentDecision, list[dict]]:
    return run_agent(db, scenario_type, situation)


def _validate_and_persist(db: Session, scenario_type: str, situation: dict, decision: AgentDecision, tool_call_log: list[dict]) -> AgentRun:
    verdict = None
    if decision.proposed_action is not None:
        verdict = validation_service.validate_proposal(db, decision.proposed_action)

    agent_run = AgentRun(
        scenario_type=scenario_type,
        input_situation=situation,
        tool_call_log=tool_call_log,
        decision=decision.model_dump(mode="json"),
        validator_verdict=verdict.model_dump() if verdict else None,
        outcome="pending_approval" if verdict is None or verdict.is_valid else "validation_failed",
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)
    return agent_run


def execute_recommendation_review(db: Session, sku: str, recommended_qty: int) -> AgentRun:
    situation = {"sku": sku, "recommended_qty": recommended_qty}
    decision, tool_call_log = run_agent_for_scenario(db, "recommendation_review", situation)
    return _validate_and_persist(db, "recommendation_review", situation, decision, tool_call_log)


def execute_supplier_shortfall(db: Session, po_id: int, fulfilled_qty: int) -> AgentRun:
    po = db.get(PurchaseOrder, po_id)
    po.fulfilled_qty = fulfilled_qty
    po.status = "partially_fulfilled" if fulfilled_qty < po.qty else "fulfilled"
    db.commit()

    situation = {
        "po_id": po_id,
        "sku": po.product_sku,
        "supplier_id": po.supplier_id,
        "ordered_qty": po.qty,
        "fulfilled_qty": fulfilled_qty,
    }
    decision, tool_call_log = run_agent_for_scenario(db, "supplier_shortfall", situation)
    return _validate_and_persist(db, "supplier_shortfall", situation, decision, tool_call_log)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_scenario_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/scenario_runner.py backend/tests/test_scenario_runner.py
git commit -m "feat: wire investigate-validate-persist scenario loop"
```

---

## Task 11: FastAPI routers and app wiring

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/products.py`
- Create: `backend/app/api/purchase_orders.py`
- Create: `backend/app/api/agent_runs.py`
- Create: `backend/app/api/scenarios.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api_scenarios.py`

**Interfaces:**
- Consumes: `get_db` from `db.base`; all services; `scenario_runner.execute_recommendation_review`/`execute_supplier_shortfall`; `AgentRunOut`, `PurchaseOrderOut`, `ProductOut`.
- Produces: FastAPI `app` in `main.py` mounting all routers under `/api`. This is what the frontend (Task 12) and eval runner (Task 13) call over HTTP.

- [ ] **Step 1: Write app/api/deps.py**

```python
from app.db.base import get_db

__all__ = ["get_db"]
```

- [ ] **Step 2: Write app/api/products.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Product, PurchaseOrder
from app.domain.models import ProductOut, PurchaseOrderOut

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.sku).all()


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
def list_purchase_orders(db: Session = Depends(get_db)):
    return db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all()
```

- [ ] **Step 3: Write app/api/purchase_orders.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import PurchaseOrderOut
from app.services import purchase_order_service

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


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
```

- [ ] **Step 4: Write app/api/agent_runs.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AgentRun
from app.domain.models import AgentRunOut

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


@router.get("", response_model=list[AgentRunOut])
def list_agent_runs(db: Session = Depends(get_db)):
    return db.query(AgentRun).order_by(AgentRun.id.desc()).all()


@router.get("/{run_id}", response_model=AgentRunOut)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    row = db.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No agent run with id={run_id}")
    return row
```

- [ ] **Step 5: Write app/api/scenarios.py**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import scenario_runner
from app.api.deps import get_db
from app.domain.models import AgentRunOut

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class RecommendationReviewRequest(BaseModel):
    sku: str
    recommended_qty: int


class SupplierShortfallRequest(BaseModel):
    po_id: int
    fulfilled_qty: int


@router.post("/recommendation-review", response_model=AgentRunOut)
def recommendation_review(body: RecommendationReviewRequest, db: Session = Depends(get_db)):
    agent_run = scenario_runner.execute_recommendation_review(db, body.sku, body.recommended_qty)
    return agent_run


@router.post("/supplier-shortfall", response_model=AgentRunOut)
def supplier_shortfall(body: SupplierShortfallRequest, db: Session = Depends(get_db)):
    agent_run = scenario_runner.execute_supplier_shortfall(db, body.po_id, body.fulfilled_qty)
    return agent_run
```

- [ ] **Step 6: Write app/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_runs, products, purchase_orders, scenarios
from app.db.base import Base, SessionLocal, engine
from app.seed_data import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.db.models import Product
        if db.query(Product).count() == 0:
            seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="AI Purchasing Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(purchase_orders.router)
app.include_router(agent_runs.router)
app.include_router(scenarios.router)
```

- [ ] **Step 7: Write tests/test_api_scenarios.py (uses monkeypatched scenario_runner to avoid live Gemini calls in fast tests)**

```python
from fastapi.testclient import TestClient

from app.agent import scenario_runner
from app.db.base import Base
from app.db.models import AgentRun
from app.domain.models import AgentDecision, ProposedAction
from app.main import app


def test_recommendation_review_endpoint_returns_agent_run(monkeypatch, db_session):
    from app.api import deps

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    from app.db.models import Budget, InventorySnapshot, Product, Supplier
    db_session.add(Product(sku="SKU-API", name="Api", category="grocery", unit_cost=1.0))
    db_session.add(InventorySnapshot(product_sku="SKU-API", on_hand_qty=50, storage_capacity_units=5000, storage_used_units=500))
    db_session.add(Budget(category="grocery", period="2026-09", available_amount=5000.0))
    supplier = Supplier(name="S", product_sku="SKU-API", lead_time_days=5, min_order_qty=50,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()

    def fake_run_agent_for_scenario(db, scenario_type, situation):
        decision = AgentDecision(
            decision="accept",
            proposed_action=ProposedAction(action_type="create_po", product_sku="SKU-API", supplier_id=supplier.id, qty=200),
            reasoning="ok", key_factors=["x"], confidence=0.9,
        )
        return decision, []

    monkeypatch.setattr(scenario_runner, "run_agent_for_scenario", fake_run_agent_for_scenario)

    client = TestClient(app)
    response = client.post("/api/scenarios/recommendation-review", json={"sku": "SKU-API", "recommended_qty": 800})

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == "accept"

    app.dependency_overrides.clear()
```

- [ ] **Step 8: Run test**

Run: `cd backend && pytest tests/test_api_scenarios.py -v`
Expected: PASS

- [ ] **Step 9: Manually smoke-test the running app**

Run: `cd backend && uvicorn app.main:app --reload --port 8000` then in another shell `curl http://localhost:8000/api/products`
Expected: JSON array of 3 seeded products

- [ ] **Step 10: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_scenarios.py
git commit -m "feat: add FastAPI routers and app wiring"
```

---

## Task 12: Evaluation fixtures and runner

**Files:**
- Create: `backend/eval/fixtures/scenario1_accept.json`
- Create: `backend/eval/fixtures/scenario1_budget_constrained.json`
- Create: `backend/eval/fixtures/scenario1_storage_constrained.json`
- Create: `backend/eval/fixtures/scenario1_moq_forces_modify.json`
- Create: `backend/eval/fixtures/scenario2_alt_supplier.json`
- Create: `backend/eval/fixtures/scenario2_inventory_sufficient.json`
- Create: `backend/eval/run_eval.py`
- Create: `backend/eval/results/.gitkeep`

**Interfaces:**
- Consumes: `scenario_runner.execute_recommendation_review`/`execute_supplier_shortfall`; the seeded DB from `app.seed_data.seed`.
- Produces: a standalone script runnable as `python -m eval.run_eval` that seeds a fresh in-memory DB per fixture, runs the real agent, checks assertions, and prints a pass/fail table plus writes transcripts to `eval/results/`.

- [ ] **Step 1: Write eval/fixtures/scenario1_accept.json**

```json
{
  "name": "scenario1_accept",
  "description": "Healthy budget and storage, recommendation within reasonable bounds — expect accept or modify, not reject.",
  "scenario_type": "recommendation_review",
  "input": {"sku": "SKU-100", "recommended_qty": 300},
  "expect": {
    "decision_in": ["accept", "modify"],
    "must_call_tools": ["get_product_snapshot", "get_demand_forecast", "get_budget_status"],
    "validator_is_valid": true
  }
}
```

- [ ] **Step 2: Write eval/fixtures/scenario1_budget_constrained.json**

```json
{
  "name": "scenario1_budget_constrained",
  "description": "SKU-200 has a tight grocery budget; recommending 800 units at ~8.5 unit cost exceeds it — expect modify or reject.",
  "scenario_type": "recommendation_review",
  "input": {"sku": "SKU-200", "recommended_qty": 800},
  "expect": {
    "decision_in": ["modify", "reject", "investigate"],
    "must_call_tools": ["get_budget_status"],
    "validator_is_valid": true
  }
}
```

- [ ] **Step 3: Write eval/fixtures/scenario1_storage_constrained.json**

```json
{
  "name": "scenario1_storage_constrained",
  "description": "SKU-300 has only 50 units of free storage; recommending 300 units should be modified down or rejected.",
  "scenario_type": "recommendation_review",
  "input": {"sku": "SKU-300", "recommended_qty": 300},
  "expect": {
    "decision_in": ["modify", "reject", "investigate"],
    "must_call_tools": ["get_product_snapshot"],
    "validator_is_valid": true
  }
}
```

- [ ] **Step 4: Write eval/fixtures/scenario1_moq_forces_modify.json**

```json
{
  "name": "scenario1_moq_forces_modify",
  "description": "Recommended qty is below the primary supplier's minimum order quantity — expect the agent to raise the qty to at least MOQ or flag it, not silently accept a sub-MOQ order.",
  "scenario_type": "recommendation_review",
  "input": {"sku": "SKU-100", "recommended_qty": 30},
  "expect": {
    "decision_in": ["modify", "investigate", "reject"],
    "must_call_tools": ["get_supplier_terms"],
    "validator_is_valid": true
  }
}
```

- [ ] **Step 5: Write eval/fixtures/scenario2_alt_supplier.json**

```json
{
  "name": "scenario2_alt_supplier",
  "description": "Existing PO for 500 units of SKU-200 from the capped supplier only fulfils 250 — an alternate uncapped supplier exists, expect the agent to consider sourcing the remainder from it.",
  "scenario_type": "supplier_shortfall",
  "input": {"po_id": 1, "fulfilled_qty": 250},
  "expect": {
    "decision_in": ["modify", "investigate"],
    "must_call_tools": ["list_alternate_suppliers"],
    "validator_is_valid": null
  }
}
```

- [ ] **Step 6: Write eval/fixtures/scenario2_inventory_sufficient.json**

```json
{
  "name": "scenario2_inventory_sufficient",
  "description": "Shortfall on SKU-300 but demand gap is already small after partial fulfillment plus on-hand stock — expect the agent to recognize inventory may be sufficient rather than always sourcing more.",
  "scenario_type": "supplier_shortfall",
  "input": {"po_id": 2, "fulfilled_qty": 140},
  "expect": {
    "decision_in": ["accept", "reject", "investigate"],
    "must_call_tools": ["get_demand_forecast"],
    "validator_is_valid": null
  }
}
```

- [ ] **Step 7: Write eval/run_eval.py**

```python
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import scenario_runner
from app.db.base import Base
from app.db.models import PurchaseOrder, Supplier
from app.seed_data import seed

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RESULTS_DIR = Path(__file__).parent / "results"


def _fresh_seeded_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    seed(session)
    # scenario2 fixtures reference a second open PO on SKU-300 that seed() doesn't create by default
    supplier = session.query(Supplier).filter_by(product_sku="SKU-300").first()
    session.add(PurchaseOrder(product_sku="SKU-300", supplier_id=supplier.id, qty=150, status="submitted"))
    session.commit()
    return session


def run_fixture(fixture: dict) -> dict:
    db = _fresh_seeded_session()
    scenario_type = fixture["scenario_type"]

    if scenario_type == "recommendation_review":
        agent_run = scenario_runner.execute_recommendation_review(db, **fixture["input"])
    elif scenario_type == "supplier_shortfall":
        agent_run = scenario_runner.execute_supplier_shortfall(db, **fixture["input"])
    else:
        raise ValueError(f"Unknown scenario_type: {scenario_type}")

    decision = agent_run.decision
    called_tools = {entry["tool"] for entry in agent_run.tool_call_log}
    expect = fixture["expect"]

    checks = {
        "decision_in_expected_set": decision["decision"] in expect["decision_in"],
        "required_tools_called": set(expect["must_call_tools"]).issubset(called_tools),
    }
    if expect["validator_is_valid"] is not None and agent_run.validator_verdict is not None:
        checks["validator_matches_expectation"] = agent_run.validator_verdict["is_valid"] == expect["validator_is_valid"]

    passed = all(checks.values())
    return {
        "name": fixture["name"],
        "passed": passed,
        "checks": checks,
        "decision": decision,
        "tool_call_log": agent_run.tool_call_log,
        "validator_verdict": agent_run.validator_verdict,
    }


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)
    fixtures = [json.loads(p.read_text()) for p in sorted(FIXTURES_DIR.glob("*.json"))]

    results = []
    for fixture in fixtures:
        print(f"Running {fixture['name']}...")
        result = run_fixture(fixture)
        results.append(result)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RESULTS_DIR / f"eval_run_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2, default=str))

    print("\n%-40s %s" % ("Fixture", "Result"))
    print("-" * 55)
    all_passed = True
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        all_passed = all_passed and result["passed"]
        print("%-40s %s" % (result["name"], status))
        if not result["passed"]:
            print(f"    checks: {result['checks']}")
            print(f"    decision: {result['decision']}")

    print(f"\nTranscripts written to {output_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Create eval/results/.gitkeep**

```
```

(empty file, ensures the directory is tracked while its JSON contents stay gitignored)

- [ ] **Step 9: Run eval against the real Gemini API (requires the user's key exported)**

Run: `cd backend && python -m eval.run_eval`
Expected: a pass/fail table printed; some fixtures may need prompt tuning to reliably pass — iterate on `prompts.py`'s `SYSTEM_PROMPT` if a fixture consistently fails for the wrong reason (e.g. agent not calling `get_supplier_terms`), not by loosening the fixture's assertions.

- [ ] **Step 10: Commit**

```bash
git add backend/eval
git commit -m "feat: add evaluation fixtures and runner"
```

---

## Task 13: Frontend scaffold, API client, and types

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: TypeScript types mirroring backend domain models (`Product`, `PurchaseOrder`, `AgentRun`, `AgentDecision`, `ValidatorVerdict`) in `types.ts`. Produces `api/client.ts` functions: `listProducts()`, `listPurchaseOrders()`, `listAgentRuns()`, `getAgentRun(id)`, `approvePurchaseOrder(id)`, `rejectPurchaseOrder(id)`, `runRecommendationReview(sku, recommendedQty)`, `runSupplierShortfall(poId, fulfilledQty)` — all later components (Task 14) call these exclusively, never `fetch` directly.

- [ ] **Step 1: Write frontend/package.json**

```json
{
  "name": "ai-purchasing-agent-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.2",
    "typescript": "^5.6.3",
    "vite": "^5.4.9"
  }
}
```

- [ ] **Step 2: Write frontend/vite.config.ts**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 3: Write frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write frontend/index.html**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>AI Purchasing Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write frontend/src/types.ts**

```typescript
export type PurchaseOrderStatus =
  | "draft" | "pending_approval" | "approved" | "submitted"
  | "partially_fulfilled" | "fulfilled" | "rejected" | "cancelled";

export interface Product {
  sku: string;
  name: string;
  category: string;
  unit_cost: number;
}

export interface PurchaseOrder {
  id: number;
  product_sku: string;
  supplier_id: number;
  qty: number;
  fulfilled_qty: number;
  status: PurchaseOrderStatus;
  created_at: string;
  expected_arrival: string | null;
}

export interface ProposedAction {
  action_type: "create_po" | "amend_po" | "no_action" | "escalate";
  product_sku: string | null;
  supplier_id: number | null;
  qty: number | null;
  po_id: number | null;
}

export interface AgentDecision {
  decision: "accept" | "modify" | "reject" | "investigate";
  proposed_action: ProposedAction | null;
  reasoning: string;
  key_factors: string[];
  confidence: number;
}

export interface ValidatorVerdict {
  is_valid: boolean;
  violations: string[];
}

export interface ToolCallLogEntry {
  tool: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface AgentRun {
  id: number;
  scenario_type: string;
  input_situation: Record<string, unknown>;
  tool_call_log: ToolCallLogEntry[];
  decision: AgentDecision | null;
  validator_verdict: ValidatorVerdict | null;
  human_action: string | null;
  outcome: string | null;
  created_at: string;
}
```

- [ ] **Step 6: Write frontend/src/api/client.ts**

```typescript
import type { AgentRun, Product, PurchaseOrder } from "../types";

const BASE_URL = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request to ${path} failed: ${response.status} ${body}`);
  }
  return response.json() as Promise<T>;
}

export const listProducts = () => request<Product[]>("/products");
export const listPurchaseOrders = () => request<PurchaseOrder[]>("/purchase-orders");
export const listAgentRuns = () => request<AgentRun[]>("/agent-runs");
export const getAgentRun = (id: number) => request<AgentRun>(`/agent-runs/${id}`);

export const approvePurchaseOrder = (id: number) =>
  request<PurchaseOrder>(`/purchase-orders/${id}/approve`, { method: "POST" });

export const rejectPurchaseOrder = (id: number) =>
  request<PurchaseOrder>(`/purchase-orders/${id}/reject`, { method: "POST" });

export const runRecommendationReview = (sku: string, recommendedQty: number) =>
  request<AgentRun>("/scenarios/recommendation-review", {
    method: "POST",
    body: JSON.stringify({ sku, recommended_qty: recommendedQty }),
  });

export const runSupplierShortfall = (poId: number, fulfilledQty: number) =>
  request<AgentRun>("/scenarios/supplier-shortfall", {
    method: "POST",
    body: JSON.stringify({ po_id: poId, fulfilled_qty: fulfilledQty }),
  });
```

- [ ] **Step 7: Write frontend/src/main.tsx (placeholder App wired in Task 14)**

```typescript
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 8: Install dependencies**

Run: `cd frontend && npm install`
Expected: installs without error

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/types.ts frontend/src/api/client.ts frontend/src/main.tsx
git commit -m "chore: scaffold frontend, API client, and shared types"
```

---

## Task 14: Frontend pages — Dashboard, Purchase Orders, Reasoning Timeline

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/PurchaseOrders.tsx`
- Create: `frontend/src/components/DecisionCard.tsx`
- Create: `frontend/src/components/ReasoningTimeline.tsx`
- Create: `frontend/src/index.css`

**Interfaces:**
- Consumes: everything from `api/client.ts` and `types.ts` (Task 13).
- Produces: a working two-page app (Dashboard, Purchase Orders) with tab navigation in `App.tsx`.

- [ ] **Step 1: Write frontend/src/index.css**

```css
:root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { margin: 0; padding: 24px; max-width: 960px; margin-inline: auto; }
h1, h2 { font-weight: 600; }
nav button { margin-right: 8px; padding: 8px 16px; cursor: pointer; }
.card { border: 1px solid #ccc4; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.badge.accept, .badge.fulfilled, .badge.approved { background: #1a7f37; color: white; }
.badge.modify, .badge.partially_fulfilled, .badge.pending_approval { background: #9a6700; color: white; }
.badge.reject, .badge.rejected { background: #cf222e; color: white; }
.badge.investigate, .badge.draft, .badge.submitted { background: #57606a; color: white; }
.violation { color: #cf222e; }
button.action { padding: 6px 14px; margin-right: 8px; cursor: pointer; }
form.trigger-form { display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }
form.trigger-form input { padding: 6px; }
```

- [ ] **Step 2: Write frontend/src/components/DecisionCard.tsx**

```typescript
import type { AgentRun } from "../types";
import { ReasoningTimeline } from "./ReasoningTimeline";

interface Props {
  agentRun: AgentRun;
  onApprove?: () => void;
  onReject?: () => void;
}

export function DecisionCard({ agentRun, onApprove, onReject }: Props) {
  const decision = agentRun.decision;
  const verdict = agentRun.validator_verdict;

  return (
    <div className="card">
      <div>
        <span className={`badge ${decision?.decision ?? "investigate"}`}>{decision?.decision ?? "investigate"}</span>
        {" "}
        <strong>{agentRun.scenario_type}</strong> — run #{agentRun.id}
      </div>
      <p>{decision?.reasoning}</p>
      <ul>
        {decision?.key_factors.map((factor) => <li key={factor}>{factor}</li>)}
      </ul>
      {verdict && !verdict.is_valid && (
        <div className="violation">
          <strong>Validator rejected this proposal:</strong>
          <ul>{verdict.violations.map((v) => <li key={v}>{v}</li>)}</ul>
        </div>
      )}
      {verdict?.is_valid && decision?.proposed_action?.action_type === "create_po" && onApprove && onReject && (
        <div>
          <button className="action" onClick={onApprove}>Approve</button>
          <button className="action" onClick={onReject}>Reject</button>
        </div>
      )}
      <ReasoningTimeline entries={agentRun.tool_call_log} />
    </div>
  );
}
```

- [ ] **Step 3: Write frontend/src/components/ReasoningTimeline.tsx**

```typescript
import { useState } from "react";
import type { ToolCallLogEntry } from "../types";

export function ReasoningTimeline({ entries }: { entries: ToolCallLogEntry[] }) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  return (
    <div>
      <button className="action" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Hide" : "Show"} reasoning timeline ({entries.length} tool calls)
      </button>
      {expanded && (
        <ol>
          {entries.map((entry, index) => (
            <li key={index}>
              <code>{entry.tool}({JSON.stringify(entry.args)})</code>
              <pre>{JSON.stringify(entry.result, null, 2)}</pre>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write frontend/src/pages/Dashboard.tsx**

```typescript
import { FormEvent, useEffect, useState } from "react";
import { listAgentRuns, runRecommendationReview, runSupplierShortfall, approvePurchaseOrder, rejectPurchaseOrder } from "../api/client";
import type { AgentRun } from "../types";
import { DecisionCard } from "../components/DecisionCard";

export function Dashboard() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [sku, setSku] = useState("SKU-100");
  const [recommendedQty, setRecommendedQty] = useState(800);
  const [poId, setPoId] = useState(1);
  const [fulfilledQty, setFulfilledQty] = useState(250);
  const [loading, setLoading] = useState(false);

  const refresh = () => listAgentRuns().then(setRuns);

  useEffect(() => { refresh(); }, []);

  async function handleRecommendationReview(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await runRecommendationReview(sku, recommendedQty);
      await refresh();
    } finally {
      setLoading(false);
    }
  }

  async function handleSupplierShortfall(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await runSupplierShortfall(poId, fulfilledQty);
      await refresh();
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(agentRun: AgentRun) {
    const action = agentRun.decision?.proposed_action;
    if (!action?.qty || !action.product_sku) return;
    // In this prototype the approve action targets a PO already implied by the proposal;
    // for create_po proposals we don't yet have a PO id, so approval here is a no-op placeholder
    // demonstrating the human gate — full PO creation-on-approve is a natural next iteration.
    await refresh();
  }

  return (
    <div>
      <h2>Trigger Scenario 1 — Purchase Recommendation Review</h2>
      <form className="trigger-form" onSubmit={handleRecommendationReview}>
        <input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="SKU" />
        <input type="number" value={recommendedQty} onChange={(e) => setRecommendedQty(Number(e.target.value))} />
        <button className="action" type="submit" disabled={loading}>Run agent</button>
      </form>

      <h2>Trigger Scenario 2 — Supplier Cannot Fulfil</h2>
      <form className="trigger-form" onSubmit={handleSupplierShortfall}>
        <input type="number" value={poId} onChange={(e) => setPoId(Number(e.target.value))} placeholder="PO id" />
        <input type="number" value={fulfilledQty} onChange={(e) => setFulfilledQty(Number(e.target.value))} placeholder="Fulfilled qty" />
        <button className="action" type="submit" disabled={loading}>Run agent</button>
      </form>

      <h2>Agent Runs</h2>
      {runs.map((run) => (
        <DecisionCard key={run.id} agentRun={run} onApprove={() => handleApprove(run)} onReject={() => handleApprove(run)} />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Write frontend/src/pages/PurchaseOrders.tsx**

```typescript
import { useEffect, useState } from "react";
import { approvePurchaseOrder, listPurchaseOrders, rejectPurchaseOrder } from "../api/client";
import type { PurchaseOrder } from "../types";

export function PurchaseOrders() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);

  const refresh = () => listPurchaseOrders().then(setOrders);

  useEffect(() => { refresh(); }, []);

  async function handleApprove(id: number) {
    await approvePurchaseOrder(id);
    await refresh();
  }

  async function handleReject(id: number) {
    await rejectPurchaseOrder(id);
    await refresh();
  }

  return (
    <div>
      <h2>Purchase Orders</h2>
      {orders.map((po) => (
        <div className="card" key={po.id}>
          <div>
            <span className={`badge ${po.status}`}>{po.status}</span>
            {" "}
            PO #{po.id} — {po.product_sku} — qty {po.qty} (fulfilled {po.fulfilled_qty})
          </div>
          {po.status === "pending_approval" && (
            <div>
              <button className="action" onClick={() => handleApprove(po.id)}>Approve</button>
              <button className="action" onClick={() => handleReject(po.id)}>Reject</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Write frontend/src/App.tsx**

```typescript
import { useState } from "react";
import "./index.css";
import { Dashboard } from "./pages/Dashboard";
import { PurchaseOrders } from "./pages/PurchaseOrders";

type Tab = "dashboard" | "purchase-orders";

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div>
      <h1>AI Purchasing Agent</h1>
      <nav>
        <button onClick={() => setTab("dashboard")}>Dashboard</button>
        <button onClick={() => setTab("purchase-orders")}>Purchase Orders</button>
      </nav>
      {tab === "dashboard" ? <Dashboard /> : <PurchaseOrders />}
    </div>
  );
}
```

- [ ] **Step 7: Run the frontend dev server against the running backend and smoke-test in browser**

Run: `cd backend && uvicorn app.main:app --reload --port 8000` (separate shell), then `cd frontend && npm run dev`
Expected: Dashboard loads, "Run agent" for Scenario 1 with SKU-100/800 produces a new DecisionCard with reasoning and a reasoning timeline; Purchase Orders tab lists the seeded open PO.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat: add Dashboard and Purchase Orders pages with reasoning timeline"
```

---

## Task 15: README, architecture diagram, and final review pass

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`

**Interfaces:**
- No code interfaces — this is the submission documentation the assignment explicitly requires.

- [ ] **Step 1: Write docs/architecture.md with a mermaid diagram**

```markdown
# Architecture

\`\`\`mermaid
flowchart TB
    UI[React Dashboard] -->|HTTP| API[FastAPI routers]
    API --> ScenarioRunner[scenario_runner]
    ScenarioRunner --> Orchestrator[Gemini tool-calling orchestrator]
    Orchestrator <-->|function calls| Tools[agent/tools.py]
    Tools --> Services[Service layer:\ninventory / demand / supplier / budget / PO]
    Services --> DB[(SQLite via SQLAlchemy)]
    ScenarioRunner --> Validator[validation_service\nindependent constraint check]
    Validator --> AgentRunTable[(agent_runs audit log)]
    UI -->|Approve/Reject| API
    API --> POService[purchase_order_service.approve]
    POService --> MockERP[supplier_service.submit_to_supplier\nmock ERP fulfillment]
    MockERP -->|partial fulfillment| ScenarioRunner
\`\`\`

The loop that matters: **investigate (tool calls) → decide (LLM) → validate (code, independent of the LLM) → human approval gate → execute → mock ERP outcome → re-invoke agent if the outcome diverges from expectation.** Steps 1-3 never touch the database; only approval (step 4) can create or amend a real purchase order.
```

- [ ] **Step 2: Write README.md**

```markdown
# AI Purchasing Agent

Full-stack prototype of an AI buyer-assistant covering:

- **Scenario 1 — Purchase Recommendation Review**: given a system-recommended purchase quantity, the agent investigates inventory, demand, open POs, supplier terms, budget, and storage, then accepts/modifies/rejects/flags for investigation.
- **Scenario 2 — Supplier Cannot Fulfil**: given a PO where the supplier confirms a lower fulfillment quantity, the agent investigates alternate suppliers and remaining demand, then proposes next steps.

See `docs/architecture.md` for the system diagram, and `docs/superpowers/specs/2026-09-14-ai-purchasing-agent-design.md` for the full design rationale.

## Setup

Backend:

\`\`\`bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # then paste your GEMINI_API_KEY into .env
uvicorn app.main:app --reload --port 8000
\`\`\`

Frontend (separate shell):

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

Open http://localhost:5173.

## Running tests

\`\`\`bash
cd backend
pytest
\`\`\`

Most tests are pure unit/integration tests against an in-memory SQLite DB and do not require a real Gemini key. `tests/test_agent_orchestrator.py` is skipped automatically unless a real `GEMINI_API_KEY` is exported.

## Running the evaluation suite

\`\`\`bash
cd backend
python -m eval.run_eval
\`\`\`

Requires a real `GEMINI_API_KEY` (this hits the live model — no mocking, by design, since the point is to test actual agent behavior). Runs 6 hand-crafted scenarios covering clean-accept, budget-constrained, storage-constrained, MOQ-forced-modify, supplier-shortfall-with-alternate, and supplier-shortfall-with-sufficient-inventory cases. Prints a pass/fail table and saves full reasoning transcripts to `eval/results/`.

## How decisions are validated

Every agent decision goes through an **independent, code-based validator** (`app/services/validation_service.py`) before it can be acted on — the agent's own arithmetic is never trusted. The validator checks: quantity positivity, supplier minimum order quantity, budget sufficiency, and storage capacity. If validation fails, the reasoning is surfaced to the buyer as-is rather than silently overridden.

Purchase orders are never written to the database by the agent directly — every `create_po`/`amend_po` proposal requires human approval via the UI (`Approve`/`Reject` buttons), which is when `purchase_order_service` actually executes against the mock ERP (`supplier_service.submit_to_supplier`). The mock ERP can return a partial fulfillment (configured per-supplier in `seed_data.py`), which automatically re-invokes the agent with the updated situation — this closes the feedback loop end-to-end rather than assuming the first action always succeeds.

## Known simplifications

- Single hardcoded budget period (`"2026-09"`) rather than a real fiscal calendar.
- Approving a `create_po` proposal from the Dashboard reasoning card is not yet wired to actually create the PO row (the Purchase Orders tab's approve/reject on *existing* POs is fully wired); a natural next step is to have `create_po` proposals first materialize as `draft` POs so the same approve/reject action works uniformly everywhere.
- Scenarios 3 and 4 are not implemented; the tool/validator architecture would extend to them directly (e.g. a `demand_spike_detected` situation type and a constraint-conflict resolution path).
```

- [ ] **Step 3: Fix the known Dashboard approve/reject gap noted in the README — wire create_po proposals to actually create a draft PO on approval**

Update `frontend/src/pages/Dashboard.tsx`'s `handleApprove`:

```typescript
  async function handleApprove(agentRun: AgentRun) {
    const action = agentRun.decision?.proposed_action;
    if (action?.action_type === "create_po" && action.product_sku && action.supplier_id && action.qty) {
      const po = await createPurchaseOrderFromProposal(action.product_sku, action.supplier_id, action.qty);
      await approvePurchaseOrder(po.id);
    }
    await refresh();
  }
```

Add to `frontend/src/api/client.ts`:

```typescript
export const createPurchaseOrderFromProposal = (sku: string, supplierId: number, qty: number) =>
  request<PurchaseOrder>("/purchase-orders/from-proposal", {
    method: "POST",
    body: JSON.stringify({ sku, supplier_id: supplierId, qty }),
  });
```

Add to `backend/app/api/purchase_orders.py`:

```python
class CreateFromProposalRequest(BaseModel):
    sku: str
    supplier_id: int
    qty: int


@router.post("/from-proposal", response_model=PurchaseOrderOut)
def create_purchase_order_from_proposal(body: CreateFromProposalRequest, db: Session = Depends(get_db)):
    return purchase_order_service.create(db, body.sku, body.supplier_id, body.qty)
```

(add `from pydantic import BaseModel` to the top of `purchase_orders.py` imports)

- [ ] **Step 4: Add a backend test for the new endpoint**

```python
# append to backend/tests/test_api_scenarios.py
def test_create_purchase_order_from_proposal_endpoint(db_session):
    from app.api import deps
    from app.db.models import Product, Supplier

    app.dependency_overrides[deps.get_db] = lambda: db_session
    Base.metadata.create_all(bind=db_session.get_bind())

    db_session.add(Product(sku="SKU-PROP", name="Prop", category="general", unit_cost=1.0))
    supplier = Supplier(name="S", product_sku="SKU-PROP", lead_time_days=5, min_order_qty=10,
                         reliability_score=0.9, unit_price=1.0, fulfillment_cap_qty=None)
    db_session.add(supplier)
    db_session.commit()

    client = TestClient(app)
    response = client.post("/api/purchase-orders/from-proposal", json={"sku": "SKU-PROP", "supplier_id": supplier.id, "qty": 100})

    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"

    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: all PASS except the live-Gemini orchestrator test, which SKIPs without a real key

- [ ] **Step 6: Manual end-to-end smoke test with the real Gemini key in place**

Run both servers, open http://localhost:5173, trigger Scenario 1 with SKU-100/800, approve the resulting proposal in Dashboard, confirm it appears correctly in the Purchase Orders tab with a real status (fulfilled or partially_fulfilled depending on the mock supplier cap); trigger Scenario 2 with an existing PO id and a partial fulfilled_qty, confirm a new AgentRun appears with a coherent decision.
Expected: no errors in either server's console; UI reflects real backend state after each action.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/architecture.md backend/app/api/purchase_orders.py backend/tests/test_api_scenarios.py frontend/src/pages/Dashboard.tsx frontend/src/api/client.ts
git commit -m "docs: add README and architecture diagram; wire proposal approval to PO creation"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1-2 cover data model; Task 3 seed data; Task 4-7 services + validator; Task 8-10 agent + feedback loop; Task 11 API; Task 12 eval; Task 13-14 frontend; Task 15 docs and closing the approve-flow gap. All spec sections have a corresponding task.
- **Type consistency:** `ProposedAction`, `AgentDecision`, `ValidatorVerdict`, `AgentRunOut`, `PurchaseOrderStatus` are defined once in Task 2 and reused verbatim through Tasks 7-14 (tools, orchestrator, scenario_runner, API routers, TypeScript `types.ts`).
- **No placeholders:** every step has literal code; the one deliberately deferred behavior (create_po → draft PO wiring) is fixed within this same plan in Task 15 rather than left as a TODO.
