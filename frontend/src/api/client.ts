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

export const createPurchaseOrderFromProposal = (sku: string, supplierId: number, qty: number) =>
  request<PurchaseOrder>("/purchase-orders/from-proposal", {
    method: "POST",
    body: JSON.stringify({ sku, supplier_id: supplierId, qty }),
  });

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
