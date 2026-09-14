export type PurchaseOrderStatus =
  | "draft" | "pending_approval" | "approved" | "submitted"
  | "partially_fulfilled" | "fulfilled" | "rejected" | "cancelled";

export interface Product {
  sku: string;
  name: string;
  category: string;
  unit_cost: number;
}

export interface PurchaseOrder {
  id: number;
  product_sku: string;
  supplier_id: number;
  qty: number;
  fulfilled_qty: number;
  status: PurchaseOrderStatus;
  created_at: string;
  expected_arrival: string | null;
}

export interface ProposedAction {
  action_type: "create_po" | "amend_po" | "no_action" | "escalate";
  product_sku: string | null;
  supplier_id: number | null;
  qty: number | null;
  po_id: number | null;
}

export interface AgentDecision {
  decision: "accept" | "modify" | "reject" | "investigate";
  proposed_action: ProposedAction | null;
  reasoning: string;
  key_factors: string[];
  confidence: number;
}

export interface ValidatorVerdict {
  is_valid: boolean;
  violations: string[];
}

export interface ToolCallLogEntry {
  tool: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface AgentRun {
  id: number;
  scenario_type: string;
  input_situation: Record<string, unknown>;
  tool_call_log: ToolCallLogEntry[];
  decision: AgentDecision | null;
  validator_verdict: ValidatorVerdict | null;
  human_action: string | null;
  outcome: string | null;
  created_at: string;
}
