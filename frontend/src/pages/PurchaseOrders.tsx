import { useEffect, useState } from "react";
import { approvePurchaseOrder, listPurchaseOrders, rejectPurchaseOrder } from "../api/client";
import type { PurchaseOrder } from "../types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Waiting for approval",
  approved: "Approved",
  submitted: "Sent to supplier",
  partially_fulfilled: "Partially fulfilled",
  fulfilled: "Fulfilled",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export function PurchaseOrders() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => listPurchaseOrders().then(setOrders);

  useEffect(() => { refresh(); }, []);

  async function handleApprove(id: number) {
    setError(null);
    try {
      await approvePurchaseOrder(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That approval did not go through.");
    }
  }

  async function handleReject(id: number) {
    setError(null);
    try {
      await rejectPurchaseOrder(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That rejection did not go through.");
    }
  }

  return (
    <div>
      <h2 className="section-title">Purchase orders</h2>
      <p className="section-hint">Every order the agent has proposed, whether it's waiting on you or already sent.</p>
      {error && <div className="error-note">{error}</div>}
      {orders.length === 0 ? (
        <div className="empty-state">No purchase orders yet.</div>
      ) : (
        orders.map((po) => (
          <div className="po-row" key={po.id}>
            <div className="po-desc">
              <span className={`status-tag ${po.status}`}>{STATUS_LABELS[po.status] ?? po.status}</span>
              Order #{po.id}, <span className="sku">{po.product_sku}</span>, {po.qty} units requested
              {po.fulfilled_qty > 0 && po.fulfilled_qty !== po.qty && ` (${po.fulfilled_qty} confirmed)`}
            </div>
            {po.status === "pending_approval" && (
              <div className="action-row">
                <button className="text-action" onClick={() => handleApprove(po.id)}>Approve</button>
                <button className="text-action reject" onClick={() => handleReject(po.id)}>Reject</button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
