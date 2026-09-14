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
