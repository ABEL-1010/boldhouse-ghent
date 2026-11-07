import type { Action, RuleId, SentinelEvent } from "./types";

/** Reserved status colors (good / warning / critical); always shown with an icon + label. */
export const ACTION_STYLE: Record<
  Action,
  { label: string; color: string; badgeClass: string; borderClass: string }
> = {
  ALLOW: {
    label: "Allowed",
    color: "#0ca30c",
    badgeClass: "bg-[#0ca30c]/10 text-[#087a08]",
    borderClass: "border-l-[#0ca30c]",
  },
  FLAG: {
    label: "Flagged",
    color: "#fab219",
    badgeClass: "bg-[#fab219]/15 text-[#8a5a00]",
    borderClass: "border-l-[#fab219]",
  },
  PAUSE: {
    label: "Paused",
    color: "#d03b3b",
    badgeClass: "bg-[#d03b3b]/10 text-[#a32626]",
    borderClass: "border-l-[#d03b3b]",
  },
};

export const RULE_LABELS: Record<RuleId, string> = {
  sensitive_read: "Reads a sensitive file (credentials, keys, .env)",
  unknown_destination: "Sends data to a destination that is not on the allowlist",
  destructive_outside_tmp: "Deletes or overwrites files outside tmp/",
  honeytoken: "Contains a honeytoken: a planted fake secret is leaving",
};

/** The path, URL or recipient a call acts on, for one-line display. */
export function targetOf(event: SentinelEvent): string {
  const { path, url, to } = event.args;
  const target = path ?? url ?? to;
  return typeof target === "string" ? target : "";
}

/** Plain-language reasons for a risk score, strongest evidence first. */
export function reasonsFor(event: SentinelEvent): string[] {
  const { signals } = event;
  const reasons: string[] = [];
  if (signals.taint) reasons.push("Data read from a sensitive file is in this outbound call (taint)");
  reasons.push(...signals.rules.map((rule) => RULE_LABELS[rule]));
  if (signals.ml_risk >= 0.5) reasons.push("Unusual compared to normal agent behaviour (ML)");
  if (signals.markov_risk >= 0.5) reasons.push("Unusual order of actions for this agent (sequence model)");
  return reasons;
}
