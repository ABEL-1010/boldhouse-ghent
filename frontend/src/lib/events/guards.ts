import type { Action, SentinelEvent, StreamEventType, ToolName } from "./types";

const TOOLS: readonly ToolName[] = [
  "read_file",
  "write_file",
  "delete_file",
  "list_dir",
  "fetch_url",
  "send_email",
  "http_post",
];
const ACTIONS: readonly Action[] = ["ALLOW", "FLAG", "PAUSE"];

export const STREAM_EVENT_TYPES: readonly StreamEventType[] = [
  "created",
  "explained",
  "decided",
  "completed",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRisk(value: unknown): value is number {
  return typeof value === "number" && value >= 0 && value <= 1;
}

/** Runtime check for SSE payloads: the network is not trusted to match our types. */
export function isSentinelEvent(value: unknown): value is SentinelEvent {
  if (!isRecord(value) || !isRecord(value.signals) || !isRecord(value.args)) return false;
  const { signals } = value;
  return (
    typeof value.event_id === "string" &&
    typeof value.session_id === "string" &&
    typeof value.step === "number" &&
    typeof value.ts === "string" &&
    TOOLS.includes(value.tool as ToolName) &&
    ACTIONS.includes(value.action as Action) &&
    isRisk(value.risk) &&
    Array.isArray(signals.rules) &&
    typeof signals.taint === "boolean" &&
    isRisk(signals.ml_risk) &&
    isRisk(signals.markov_risk) &&
    (value.explanation === null || isRecord(value.explanation)) &&
    (value.decision === null || isRecord(value.decision)) &&
    (value.result === null || isRecord(value.result))
  );
}
