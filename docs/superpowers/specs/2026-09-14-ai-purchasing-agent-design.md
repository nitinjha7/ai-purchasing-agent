# AI Purchasing Agent — Design Spec

Date: 2026-09-14
Status: Approved for implementation

## Problem

Build a full-stack AI Purchasing Agent (Rappi assignment) covering:

- **Scenario 1** — Purchase Recommendation Review: system recommends buying 800 units; agent must investigate inventory, demand, open POs, supplier lead time/MOQ, budget, and storage capacity, then accept/modify/reject/investigate-further with reasoning.
- **Scenario 2** — Supplier Cannot Fulfil: PO for 500 units, supplier confirms only 250. Agent must decide next action (source elsewhere, alt supplier, new PO, inventory sufficient, escalate), gathering whatever additional info it needs first.

Both scenarios must run end-to-end with a working feedback/validation loop: after the agent proposes or executes an action, the system independently verifies whether the outcome was actually acceptable, and reacts if it wasn't.

## Non-goals

- Scenarios 3 and 4 (not implemented; architecture would support them but out of scope for the time budget).
- Production infra (auth, real Postgres, deployment). Mock data/services throughout, but structured as if backed by real systems.
- A general-purpose purchasing chatbot. The system executes and validates decisions, it does not just answer questions.

## Architecture

```
backend/                     FastAPI app
  app/
    domain/                  Pydantic models: Product, Supplier, PurchaseOrder,
                              InventorySnapshot, DemandForecast, AgentRun, ToolCallLog
    db/                      SQLAlchemy models + session mgmt (SQLite file; swappable
                              to Postgres via DATABASE_URL only)
    services/                Pure business logic, no LLM awareness
      inventory_service.py       stock levels, storage capacity checks
      demand_service.py          forecast lookup, demand-vs-supply math
      supplier_service.py        lead time, MOQ, reliability, alt-supplier lookup,
                                  mock ERP fulfillment behavior
      budget_service.py          available budget checks
      purchase_order_service.py  create/modify/cancel PO, status transitions
      validation_service.py      independent post-decision constraint verification
    agent/                   Gemini orchestration
      tools.py                   tool schema + dispatch to services
      orchestrator.py            tool-calling loop, forces structured final decision
      prompts.py                 system prompt / decision framework text
    api/                     FastAPI routers, thin — call services/agent only
      scenarios.py
      purchase_orders.py
      agent_runs.py
      products.py
    seed_data.py              deterministic mock dataset
  eval/
    fixtures/                 hand-crafted scenario cases (JSON)
    run_eval.py                runs fixtures against the live agent, prints pass/fail
    results/                   saved reasoning transcripts
  tests/                       pytest unit tests for services + validator
  alembic/                     migrations (real DB story, not toy)
  main.py
  .env.example

frontend/                    Vite + React + TypeScript
  src/
    pages/Dashboard.tsx          pending agent recommendations, approve/reject
    pages/PurchaseOrders.tsx     PO list + status
    components/ReasoningTimeline.tsx   expandable tool-call trace per AgentRun
    api/client.ts

docs/
  architecture.md (mermaid diagram)
README.md
```

## Data model (mock "ERP", real shape)

- **Product**: sku, name, category, unit_cost
- **InventorySnapshot**: product_sku, on_hand_qty, storage_capacity_units, storage_used_units
- **DemandForecast**: product_sku, horizon_days, forecast_qty, recent_actual_sales_qty
- **Supplier**: id, name, lead_time_days, min_order_qty, reliability_score, unit_price
- **PurchaseOrder**: id, product_sku, supplier_id, qty, status (draft/pending_approval/approved/submitted/partially_fulfilled/fulfilled/rejected/cancelled), created_at, expected_arrival
- **Budget**: category, period, available_amount
- **AgentRun**: id, scenario_type, input_situation, tool_call_log (JSON), decision (JSON), validator_verdict (JSON), human_action, outcome, created_at

Mock ERP fulfillment behavior lives in `supplier_service.submit_to_supplier(po)`: each seeded supplier has a deterministic fulfillment rule (e.g. "fulfills in full if qty <= 600, else caps at 250") so Scenario 2 is reproducible, not randomized.

## Agent design

Gemini (via `google-generativeai` / `google-genai` SDK) is given a system prompt describing its role as a purchasing buyer-assistant and a decision framework, plus tools:

- `get_product_snapshot(sku)`
- `get_demand_forecast(sku)`
- `get_open_purchase_orders(sku)`
- `get_supplier_terms(sku, supplier_id)`
- `get_budget_status(category)`
- `list_alternate_suppliers(sku)`
- `propose_purchase_order(sku, supplier_id, qty, rationale)` — returns a structured proposal, does not write to DB
- `propose_po_amendment(po_id, new_qty, rationale)`

The orchestrator runs a bounded tool-calling loop (max 8 turns) and requires the model's final turn to emit a JSON object validated against a Pydantic schema: `{decision: accept|modify|reject|investigate, proposed_action, reasoning, key_factors: [...], confidence}`. If the model fails to produce valid JSON within the turn budget, the run is marked `investigate` with an error note (fail safe, never silently guess).

## Feedback / validation loop

1. Agent investigates via tools, emits decision + proposed action.
2. `validation_service` independently re-checks the proposed action in code (budget, storage, MOQ, no duplicate open PO for same need) — ground truth, not trusting the LLM's arithmetic.
3. If validation fails, the failure reason is fed back to the agent as a tool result and it gets **one** revision attempt; if still invalid, status becomes `investigate` for a human.
4. If validation passes and the action would create/modify a real PO, status = `pending_approval` — buyer must approve in the UI before anything is written.
5. On approval, `purchase_order_service` executes for real and calls the mock ERP `submit_to_supplier`, which may return partial fulfillment.
6. Partial/failed fulfillment automatically re-invokes the agent with the updated situation (this is the Scenario 2 trigger path when reached via Scenario 1's approved PO, and also the direct entry point for Scenario 2's standalone test cases).
7. Every tool call, decision, validator verdict, human action, and ERP response is persisted as an `AgentRun` — read by both the UI reasoning timeline and the eval suite.

## API surface

- `POST /api/scenarios/recommendation-review` — {sku, recommended_qty} → AgentRun
- `POST /api/scenarios/supplier-shortfall` — {po_id, fulfilled_qty} → AgentRun
- `GET /api/agent-runs`, `GET /api/agent-runs/{id}`
- `POST /api/purchase-orders/{id}/approve`, `POST /api/purchase-orders/{id}/reject`
- `GET /api/products`, `GET /api/purchase-orders`

## Frontend

Minimal React + TypeScript, no CSS framework: Buyer Dashboard (pending recommendation cards with reasoning + validator verdict + approve/reject), PO list with status, expandable reasoning timeline per AgentRun.

## Evaluation approach

`eval/fixtures/` — 6-8 seeded scenario variants covering: clean accept, budget-constrained modify, storage-constrained modify/reject, MOQ-forced modify, supplier-shortfall resolved via alternate supplier, supplier-shortfall where existing inventory is sufficient (reject further purchase). Each fixture asserts:

- expected decision type
- specific tools were called (proof of investigation, not a rubber stamp)
- validator agrees with the final action
- no resulting PO violates budget/storage/MOQ constraints

`eval/run_eval.py` runs all fixtures against the live Gemini API (no mocking — real key required, per user decision) and prints a pass/fail table, saving full reasoning transcripts to `eval/results/` for inclusion in the README.

## Environment / secrets

`.env` (gitignored) holds `GEMINI_API_KEY` and `DATABASE_URL` (defaults to local SQLite file). `.env.example` documents both with no real values. User will paste their own Gemini key locally; it is never committed.

## Open risks / decisions accepted

- No mocked-LLM fallback mode — eval and demo both require a live Gemini key (explicit user choice).
- SQLite instead of real Postgres for zero-setup review; schema/service layer written so swapping is a connection-string change only.
- Scenarios 3/4 not implemented; noted as future extension in README given shared architecture.
