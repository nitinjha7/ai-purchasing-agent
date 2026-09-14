import type { AgentRun } from "../types";
import { ReasoningTimeline } from "./ReasoningTimeline";

interface Props {
  agentRun: AgentRun;
  onApprove?: () => void;
  onReject?: () => void;
}

export function DecisionCard({ agentRun, onApprove, onReject }: Props) {
  const decision = agentRun.decision;
  const verdict = agentRun.validator_verdict;
  const actionType = decision?.proposed_action?.action_type;
  const isExecutable = actionType === "create_po" || actionType === "amend_po";

  return (
    <div className="card">
      <div>
        <span className={`badge ${decision?.decision ?? "investigate"}`}>{decision?.decision ?? "investigate"}</span>
        {" "}
        <strong>{agentRun.scenario_type}</strong> — run #{agentRun.id}
      </div>
      <p>{decision?.reasoning}</p>
      <ul>
        {decision?.key_factors.map((factor) => <li key={factor}>{factor}</li>)}
      </ul>
      {verdict && !verdict.is_valid && (
        <div className="violation">
          <strong>Validator rejected this proposal:</strong>
          <ul>{verdict.violations.map((v) => <li key={v}>{v}</li>)}</ul>
        </div>
      )}
      {agentRun.human_action && (
        <p><strong>Buyer action:</strong> {agentRun.human_action}</p>
      )}
      {verdict?.is_valid && isExecutable && !agentRun.human_action && onApprove && onReject && (
        <div>
          <button className="action" onClick={onApprove}>Approve</button>
          <button className="action" onClick={onReject}>Reject</button>
        </div>
      )}
      <ReasoningTimeline entries={agentRun.tool_call_log} />
    </div>
  );
}
