import { useState } from "react";
import type { ToolCallLogEntry } from "../types";

export function ReasoningTimeline({ entries }: { entries: ToolCallLogEntry[] }) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  return (
    <div>
      <button className="action" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Hide" : "Show"} reasoning timeline ({entries.length} tool calls)
      </button>
      {expanded && (
        <ol>
          {entries.map((entry, index) => (
            <li key={index}>
              <code>{entry.tool}({JSON.stringify(entry.args)})</code>
              <pre>{JSON.stringify(entry.result, null, 2)}</pre>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
