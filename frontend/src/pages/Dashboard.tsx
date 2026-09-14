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
    if (action?.action_type === "create_po") {
      const po = await createPurchaseOrderFromProposal(agentRun.id);
      await approvePurchaseOrder(po.id);
    } else if (action?.action_type === "amend_po") {
      await amendPurchaseOrderFromProposal(agentRun.id);
    }
    await refresh();
  }

  async function handleReject(agentRun: AgentRun) {
    await rejectAgentRun(agentRun.id);
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
        <DecisionCard key={run.id} agentRun={run} onApprove={() => handleApprove(run)} onReject={() => handleReject(run)} />
      ))}
    </div>
  );
}
