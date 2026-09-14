# AI Purchasing Agent

Full-stack prototype of an AI buyer-assistant covering:

- **Scenario 1 — Purchase Recommendation Review**: given a system-recommended purchase quantity, the agent investigates inventory, demand, open POs, supplier terms, budget, and storage, then accepts/modifies/rejects/flags for investigation.
- **Scenario 2 — Supplier Cannot Fulfil**: given a PO where the supplier confirms a lower fulfillment quantity, the agent investigates alternate suppliers and remaining demand, then proposes next steps.

See `docs/architecture.md` for the system diagram, and `docs/superpowers/specs/2026-09-14-ai-purchasing-agent-design.md` for the full design rationale.

## Setup

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # then paste your GEMINI_API_KEY into .env
uvicorn app.main:app --reload --port 8000
```

Frontend (separate shell):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Running tests

```bash
cd backend
pytest
```

Most tests are pure unit/integration tests against an in-memory SQLite DB and do not require a real Gemini key. `tests/test_agent_orchestrator.py` is skipped automatically unless a real `GEMINI_API_KEY` is exported.

## Running the evaluation suite

```bash
cd backend
python -m eval.run_eval
```

Requires a real `GEMINI_API_KEY` (this hits the live model — no mocking, by design, since the point is to test actual agent behavior). Runs 6 hand-crafted scenarios covering clean-accept, budget-constrained, storage-constrained, MOQ-forced-modify, supplier-shortfall-with-alternate, and supplier-shortfall-with-sufficient-inventory cases. Prints a pass/fail table and saves full reasoning transcripts to `eval/results/`.

## How decisions are validated

Every agent decision goes through an **independent, code-based validator** (`app/services/validation_service.py`) before it can be acted on — the agent's own arithmetic is never trusted. The validator checks: quantity positivity, supplier minimum order quantity, budget sufficiency, and storage capacity. If validation fails, the reasoning is surfaced to the buyer as-is rather than silently overridden.

Purchase orders are never written to the database by the agent directly — every `create_po`/`amend_po` proposal requires human approval via the UI (`Approve`/`Reject` buttons). Approving a `create_po` proposal creates the PO row and immediately approves it against the mock ERP (`supplier_service.submit_to_supplier`); approving/rejecting an existing PO from the Purchase Orders tab acts on that PO directly. The mock ERP can return a partial fulfillment (configured per-supplier in `seed_data.py`), which automatically re-invokes the agent with the updated situation — this closes the feedback loop end-to-end rather than assuming the first action always succeeds.

## Known simplifications

- Single hardcoded budget period (`"2026-09"`) rather than a real fiscal calendar.
- Scenarios 3 and 4 are not implemented; the tool/validator architecture would extend to them directly (e.g. a `demand_spike_detected` situation type and a constraint-conflict resolution path).
