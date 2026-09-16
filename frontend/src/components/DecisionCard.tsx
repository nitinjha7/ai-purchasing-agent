import type { AgentRun } from "../types";
import { ReasoningTimeline } from "./ReasoningTimeline";

interface Props {
  agentRun: AgentRun;
  onApprove?: () => void;
  onReject?: () => void;
}

const SCENARIO_LABELS: Record<string, string> = {
  recommendation_review: "Purchase recommendation",
  supplier_shortfall: "Supplier shortfall",
};

const DECISION_LABELS: Record<string, string> = {
  accept: "Accepted",
  modify: "Modified",
  reject: "Rejected",
  investigate: "Needs more information",
};

export function DecisionCard({ agentRun, onApprove, onReject }: Props) {
  const decision = agentRun.decision;
  const verdict = agentRun.validator_verdict;
  const actionType = decision?.proposed_action?.action_type;
  const isExecutable = actionType === "create_po" || actionType === "amend_po";
  const decisionKey = decision?.decision ?? "investigate";

  return (
    <div className={`run-entry decision-${decisionKey}`}>
      <div className="run-head">
        <span className={`decision-label decision-${decisionKey}`}>
          {DECISION_LABELS[decisionKey] ?? decisionKey}
        </span>
        <span className="run-meta">
          {SCENARIO_LABELS[agentRun.scenario_type] ?? agentRun.scenario_type}, review #{agentRun.id}
        </span>
      </div>
      <p className="reasoning">{decision?.reasoning}</p>
      {decision?.key_factors && decision.key_factors.length > 0 && (
        <ul className="factors">
          {decision.key_factors.map((factor) => <li key={factor}>{factor}</li>)}
        </ul>
      )}
      {verdict && !verdict.is_valid && (
        <div className="violation-box">
          <span className="violation-title">This proposal doesn't clear the checks in place:</span>
          <ul>{verdict.violations.map((v) => <li key={v}>{v}</li>)}</ul>
        </div>
      )}
      {agentRun.human_action && (
        <p className="buyer-action">You {agentRun.human_action} this.</p>
      )}
      {verdict?.is_valid && isExecutable && !agentRun.human_action && onApprove && onReject && (
        <div className="action-row">
          <button className="text-action" onClick={onApprove}>Approve</button>
          <button className="text-action reject" onClick={onReject}>Reject</button>
        </div>
      )}
      <ReasoningTimeline entries={agentRun.tool_call_log} />
    </div>
  );
}
