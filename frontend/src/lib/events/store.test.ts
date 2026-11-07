import { describe, expect, it } from "vitest";

import { sampleEvents } from "./fixtures";
import {
  applyEvent,
  emptyStore,
  type EventStore,
  eventsForSession,
  outcomeOf,
  pendingDecisions,
  sessionsOf,
} from "./store";
import type { SentinelEvent } from "./types";

const [allowed, flagged, paused] = sampleEvents.map((event): SentinelEvent => structuredClone(event));

function storeOf(...events: SentinelEvent[]): EventStore {
  return events.reduce(applyEvent, emptyStore);
}

function withSession(event: SentinelEvent, sessionId: string, eventId: string, step = 1): SentinelEvent {
  return { ...event, session_id: sessionId, event_id: eventId, step };
}

describe("applyEvent", () => {
  it("replaces a snapshot with the same id instead of duplicating it", () => {
    const decided: SentinelEvent = {
      ...paused!,
      decision: { approve: false, reason: "No.", source: "human", ts: "2026-11-21T14:04:00Z" },
    };

    const store = storeOf(paused!, decided);

    expect(store.order).toEqual([paused!.event_id]);
    expect(store.byId[paused!.event_id]?.decision?.reason).toBe("No.");
  });

  it("does not mutate the previous store", () => {
    const before = storeOf(allowed!);

    applyEvent(before, flagged!);

    expect(before.order).toEqual([allowed!.event_id]);
  });
});

describe("sessions and ordering", () => {
  it("lists sessions oldest first and events by step", () => {
    const store = storeOf(
      withSession(allowed!, "s_b", "evt_b2", 2),
      withSession(allowed!, "s_a", "evt_a1", 1),
      withSession(flagged!, "s_b", "evt_b1", 1),
    );

    expect(sessionsOf(store)).toEqual(["s_b", "s_a"]);
    expect(eventsForSession(store, "s_b").map((e) => e.event_id)).toEqual(["evt_b1", "evt_b2"]);
  });
});

describe("pendingDecisions", () => {
  it("contains a PAUSE until it is decided", () => {
    const decided: SentinelEvent = {
      ...paused!,
      decision: { approve: false, reason: "No.", source: "timeout", ts: "2026-11-21T14:04:41Z" },
    };

    expect(pendingDecisions(storeOf(allowed!, flagged!, paused!))).toEqual([paused]);
    expect(pendingDecisions(storeOf(paused!, decided))).toEqual([]);
  });
});

describe("outcomeOf", () => {
  const blockedResult = { ok: false, preview: "Blocked by Sentinel: No." };

  it.each([
    ["awaiting-human", { ...paused! }],
    ["running", { ...allowed!, result: null }],
    ["executed", { ...allowed! }],
    [
      "blocked",
      {
        ...paused!,
        decision: { approve: false, reason: "No.", source: "human", ts: "t" },
        result: blockedResult,
      },
    ],
    ["failed", { ...allowed!, result: { ok: false, preview: "File not found" } }],
  ] as const)("is %s", (expected, event) => {
    expect(outcomeOf(event as SentinelEvent)).toBe(expected);
  });
});
