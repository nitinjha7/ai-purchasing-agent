# Architecture

```mermaid
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
```

The loop that matters: **investigate (tool calls) → decide (LLM) → validate (code, independent of the LLM) → human approval gate → execute → mock ERP outcome → re-invoke agent if the outcome diverges from expectation.** Steps 1-3 never touch the database; only approval (step 4) can create or amend a real purchase order.
