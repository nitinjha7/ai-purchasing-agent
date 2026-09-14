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
    Validator -->|violations: one revision attempt| Orchestrator
    Validator --> AgentRunTable[(agent_runs audit log)]
    UI -->|Approve/Reject| API
    API -->|re-validate stored proposal| Validator
    API --> POService[purchase_order_service.approve]
    POService --> MockERP[supplier_service.submit_to_supplier\nmock ERP fulfillment]
    MockERP -->|partial fulfillment| ScenarioRunner
```

The loop that matters: **investigate (tool calls) → decide (LLM) → validate (code, independent of the LLM) → revise once if the validator objects → human approval gate → execute → mock ERP outcome → re-invoke agent if the outcome diverges from expectation.** The investigate/decide/validate steps never touch the database; only approval can create or amend a real purchase order, and the approval endpoints re-derive the proposal from its stored agent run and re-run the validator before writing — the client only supplies an agent run id.

The final arrow is real code, not an aspiration: `POST /api/purchase-orders/{po_id}/approve` inspects the status the mock ERP returned and, on `partially_fulfilled`, calls `scenario_runner.execute_supplier_shortfall` with the actual fulfilled quantity, which creates a fresh agent run for the buyer to review.
