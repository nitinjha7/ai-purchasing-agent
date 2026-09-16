import { FormEvent, useEffect, useState } from "react";
import { listAgentRuns, runRecommendationReview, runSupplierShortfall, approvePurchaseOrder, createPurchaseOrderFromProposal, amendPurchaseOrderFromProposal, rejectAgentRun } from "../api/client";
import type { AgentRun } from "../types";
import { DecisionCard } from "../components/DecisionCard";

export function Dashboard() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [sku, setSku] = useState("SKU-100");
  const [recommendedQty, setRecommendedQty] = useState(800);
  const [poId, setPoId] = useState(1);
  const [fulfilledQty, setFulfilledQty] = useState(250);
  const [loadingScenario, setLoadingScenario] = useState<"review" | "shortfall" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = () => listAgentRuns().then(setRuns);

  useEffect(() => { refresh(); }, []);

  async function handleRecommendationReview(event: FormEvent) {
    event.preventDefault();
    setLoadingScenario("review");
    setActionError(null);
    try {
      await runRecommendationReview(sku, recommendedQty);
      await refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "The review could not be run.");
    } finally {
      setLoadingScenario(null);
    }
  }

  async function handleSupplierShortfall(event: FormEvent) {
    event.preventDefault();
    setLoadingScenario("shortfall");
    setActionError(null);
    try {
      await runSupplierShortfall(poId, fulfilledQty);
      await refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "The shortfall could not be reviewed.");
    } finally {
      setLoadingScenario(null);
    }
  }

  async function handleApprove(agentRun: AgentRun) {
    setActionError(null);
    const action = agentRun.decision?.proposed_action;
    try {
      if (action?.action_type === "create_po") {
        const po = await createPurchaseOrderFromProposal(agentRun.id);
        await approvePurchaseOrder(po.id);
      } else if (action?.action_type === "amend_po") {
        await amendPurchaseOrderFromProposal(agentRun.id);
      }
      await refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "That approval did not go through.");
    }
  }

  async function handleReject(agentRun: AgentRun) {
    setActionError(null);
    try {
      await rejectAgentRun(agentRun.id);
      await refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "That rejection did not go through.");
    }
  }

  return (
    <div>
      <section>
        <h2 className="section-title">Start a review</h2>
        <p className="section-hint">
          Pick a scenario below. The agent will look at inventory, demand, open orders,
          supplier terms, and budget before it decides what to do.
        </p>
        <div className="trigger-grid">
          <form className="trigger-form" onSubmit={handleRecommendationReview}>
            <label>A purchase has been recommended</label>
            <div className="field-row">
              <div style={{ flex: 2 }}>
                <label htmlFor="sku">Product</label>
                <input id="sku" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="SKU-100" />
              </div>
              <div style={{ flex: 1 }}>
                <label htmlFor="qty">Recommended units</label>
                <input id="qty" type="number" value={recommendedQty} onChange={(e) => setRecommendedQty(Number(e.target.value))} />
              </div>
            </div>
            <button className="primary" type="submit" disabled={loadingScenario !== null}>
              {loadingScenario === "review" ? "Reviewing…" : "Review this recommendation"}
            </button>
          </form>

          <form className="trigger-form" onSubmit={handleSupplierShortfall}>
            <label>A supplier can't fulfil an order in full</label>
            <div className="field-row">
              <div style={{ flex: 1 }}>
                <label htmlFor="po">Order number</label>
                <input id="po" type="number" value={poId} onChange={(e) => setPoId(Number(e.target.value))} />
              </div>
              <div style={{ flex: 1 }}>
                <label htmlFor="fulfilled">Units they can send</label>
                <input id="fulfilled" type="number" value={fulfilledQty} onChange={(e) => setFulfilledQty(Number(e.target.value))} />
              </div>
            </div>
            <button className="primary" type="submit" disabled={loadingScenario !== null}>
              {loadingScenario === "shortfall" ? "Reviewing…" : "Review this shortfall"}
            </button>
          </form>
        </div>
      </section>

      <section>
        <h2 className="section-title">Agent decisions</h2>
        <p className="section-hint">
          Most recent first. Anything that would create or change an order waits here for
          your approval.
        </p>
        {actionError && <div className="error-note">{actionError}</div>}
        {runs.length === 0 ? (
          <div className="empty-state">No reviews yet. Run one above to see the agent's reasoning here.</div>
        ) : (
          runs.map((run) => (
            <DecisionCard key={run.id} agentRun={run} onApprove={() => handleApprove(run)} onReject={() => handleReject(run)} />
          ))
        )}
      </section>
    </div>
  );
}
