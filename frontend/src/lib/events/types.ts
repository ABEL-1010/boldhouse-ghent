/**
 * The Sentinel event contract. It mirrors backend/src/sentinel/features/events/schemas.py,
 * and docs/contract/event.schema.json is the generated source of truth.
 *
 * Every SSE message carries the full event snapshot. The SSE event name (StreamEventType)
 * says what changed, so clients replace the stored event by `event_id`.
 */

export type ToolName =
  | "read_file"
  | "write_file"
  | "delete_file"
  | "list_dir"
  | "fetch_url"
  | "send_email"
  | "http_post";

export type RuleId =
  | "sensitive_read"
  | "unknown_destination"
  | "destructive_outside_tmp"
  | "honeytoken";

export type Action = "ALLOW" | "FLAG" | "PAUSE";

export type Verdict = "benign" | "suspicious" | "malicious";

export type DecisionSource = "human" | "timeout";

export type StreamEventType = "created" | "explained" | "decided" | "completed";

/** Values in [0, 1]. */
export type RiskScore = number;

/** UTC ISO-8601 timestamp, e.g. "2026-11-21T14:03:11Z". */
export type IsoTimestamp = string;

export type Signals = {
  rules: RuleId[];
  taint: boolean;
  ml_risk: RiskScore;
  markov_risk: RiskScore;
};

/** Advisory output of the Claude judge. It never changes risk or action. */
export type Explanation = {
  verdict: Verdict;
  explanation: string;
  what_to_check: string;
};

export type Decision = {
  approve: boolean;
  reason: string;
  source: DecisionSource;
  ts: IsoTimestamp;
};

export type ToolResult = {
  ok: boolean;
  /** At most 200 characters. */
  preview: string;
};

export type SentinelEvent = {
  /** Format: evt_<alphanumeric> */
  event_id: string;
  /** Format: s_<alphanumeric> */
  session_id: string;
  step: number;
  ts: IsoTimestamp;
  tool: ToolName;
  args: Record<string, unknown>;
  signals: Signals;
  risk: RiskScore;
  action: Action;
  explanation: Explanation | null;
  decision: Decision | null;
  result: ToolResult | null;
};
