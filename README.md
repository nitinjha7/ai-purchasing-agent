# AI Purchasing Agent

Full-stack prototype of an AI buyer-assistant covering:

- **Scenario 1 — Purchase Recommendation Review**: given a system-recommended purchase quantity, the agent investigates inventory, demand, open POs, supplier terms, budget, and storage, then accepts/modifies/rejects/flags for investigation.
- **Scenario 2 — Supplier Cannot Fulfil**: given a PO where the supplier confirms a lower fulfillment quantity, the agent investigates alternate suppliers and remaining demand, then proposes next steps.

See `docs/architecture.md` for the system diagram, and `docs/superpowers/specs/2026-09-14-ai-purchasing-agent-design.md` for the full design rationale.

## Deployed live link
```bash
https://ai-purchasing-agent-web.onrender.com/
```

## Setup

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # then paste your GEMINI_API_KEY into .env
uvicorn app.main:app --reload --port 8000
```

The app creates any missing tables on startup, so no migration step is required to run it. Migrations are also available if you prefer to manage the schema explicitly — `alembic upgrade head` (run from `backend/`) applies the baseline schema to the database named in `DATABASE_URL`.

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

Every agent decision goes through an **independent, code-based validator** (`app/services/validation_service.py`) before it can be acted on — the agent's own arithmetic is never trusted. The validator checks: quantity positivity, supplier minimum order quantity, budget sufficiency, and storage capacity. For an `amend_po` proposal the product and supplier are read off the referenced purchase order, so the same checks apply.

If validation fails, the violations are fed back to the agent as extra context and it gets **exactly one chance to revise** its proposal. The revised decision and verdict are what get persisted, with the tool-call logs of both attempts concatenated so the buyer sees the whole investigation. If the revision is still invalid, the failure is surfaced to the buyer as-is rather than silently overridden or retried indefinitely.

Purchase orders are never written to the database by the agent directly — every `create_po`/`amend_po` proposal requires human approval via the UI (`Approve`/`Reject` buttons). Approval posts only the agent run id: the server re-reads the proposal from the stored run, re-runs the validator, and only then writes, so nothing the client sends can bypass a constraint. Approving a `create_po` proposal creates the PO row and immediately approves it against the mock ERP (`supplier_service.submit_to_supplier`); approving an `amend_po` proposal updates the referenced PO's quantity; `Reject` records the buyer's decision on the agent run and creates nothing. Approving/rejecting an existing PO from the Purchase Orders tab acts on that PO directly.

The mock ERP can return a partial fulfillment (configured per-supplier via `fulfillment_cap_qty` in `seed_data.py`). When a PO approval comes back partially fulfilled, the approve endpoint automatically re-invokes the agent on the shortfall, producing a new agent run in the dashboard — this closes the feedback loop end-to-end rather than assuming the first action always succeeds.

## Known simplifications

- Single hardcoded budget period (`"2026-09"`) rather than a real fiscal calendar.
- Scenarios 3 and 4 are not implemented; the tool/validator architecture would extend to them directly (e.g. a `demand_spike_detected` situation type and a constraint-conflict resolution path).
- The `/approve` endpoint's automatic re-invocation of the agent on partial fulfillment runs synchronously in the request and isn't wrapped in its own error boundary: a Gemini failure at that exact point returns an error to the client even though the purchase order itself was already approved and submitted successfully. Checking the Purchase Orders tab shows the true state in that case.
- Re-approving or re-amending the same agent run id more than once is not guarded server-side (the UI hides the button after one use, but the API itself doesn't reject a replay). Each replay still passes through the same budget/storage/MOQ validation, so it can't produce an order the constraints wouldn't otherwise allow.
