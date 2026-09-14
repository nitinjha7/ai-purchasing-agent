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
      {verdict?.is_valid && decision?.proposed_action?.action_type === "create_po" && onApprove && onReject && (
        <div>
          <button className="action" onClick={onApprove}>Approve</button>
          <button className="action" onClick={onReject}>Reject</button>
        </div>
      )}
      <ReasoningTimeline entries={agentRun.tool_call_log} />
    </div>
  );
}
