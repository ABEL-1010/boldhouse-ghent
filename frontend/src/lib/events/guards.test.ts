import { describe, expect, it } from "vitest";

import { sampleEvents } from "./fixtures";
import { isSentinelEvent } from "./guards";
import { reasonsFor, targetOf } from "./labels";
import type { SentinelEvent } from "./types";

const paused: SentinelEvent = structuredClone(sampleEvents[2]);

describe("isSentinelEvent", () => {
  it("accepts every sample event, including after a JSON round-trip", () => {
    for (const event of sampleEvents) {
      expect(isSentinelEvent(JSON.parse(JSON.stringify(event)))).toBe(true);
    }
  });

  it.each([
    ["null", null],
    ["an array", []],
    ["an unknown tool", { ...paused, tool: "rm_rf" }],
    ["an unknown action", { ...paused, action: "BLOCK" }],
    ["risk above 1", { ...paused, risk: 1.5 }],
    ["missing signals", { ...paused, signals: undefined }],
    ["ml risk as text", { ...paused, signals: { ...paused.signals, ml_risk: "0.9" } }],
  ])("rejects %s", (_label, value) => {
    expect(isSentinelEvent(value)).toBe(false);
  });
});

describe("labels", () => {
  it("names the target of a call", () => {
    expect(targetOf(paused)).toBe("backup@unknown-domain.xyz");
  });

  it("explains a paused exfiltration, strongest evidence first", () => {
    const reasons = reasonsFor(paused);

    expect(reasons[0]).toMatch(/taint/);
    expect(reasons).toContain("Sends data to a destination that is not on the allowlist");
    expect(reasons.some((reason) => reason.includes("(ML)"))).toBe(true);
  });
});
