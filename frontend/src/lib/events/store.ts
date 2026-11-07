import type { SentinelEvent } from "./types";

/**
 * Client-side event state. Every SSE message is a full snapshot, so applying one simply
 * replaces the stored event with the same id. Pure functions, so they are easy to test.
 */
export type EventStore = {
  readonly byId: Readonly<Record<string, SentinelEvent>>;
  /** Event ids in order of first arrival. */
  readonly order: readonly string[];
};

export const emptyStore: EventStore = { byId: {}, order: [] };

export function applyEvent(store: EventStore, event: SentinelEvent): EventStore {
  const known = event.event_id in store.byId;
  return {
    byId: { ...store.byId, [event.event_id]: event },
    order: known ? store.order : [...store.order, event.event_id],
  };
}

function inOrder(store: EventStore): SentinelEvent[] {
  return store.order.flatMap((id) => {
    const event = store.byId[id];
    return event ? [event] : [];
  });
}

/** Session ids, oldest first. */
export function sessionsOf(store: EventStore): string[] {
  return [...new Set(inOrder(store).map((event) => event.session_id))];
}

export function eventsForSession(store: EventStore, sessionId: string): SentinelEvent[] {
  return inOrder(store)
    .filter((event) => event.session_id === sessionId)
    .sort((a, b) => a.step - b.step);
}

/** Paused actions still waiting for a human, oldest first (across all sessions). */
export function pendingDecisions(store: EventStore): SentinelEvent[] {
  return inOrder(store).filter(
    (event) => event.action === "PAUSE" && event.decision === null && event.result === null,
  );
}

export type Outcome = "awaiting-human" | "running" | "executed" | "blocked" | "failed";

export function outcomeOf(event: SentinelEvent): Outcome {
  if (event.result === null) {
    return event.action === "PAUSE" && event.decision === null ? "awaiting-human" : "running";
  }
  if (event.result.ok) return "executed";
  return event.decision?.approve === false ? "blocked" : "failed";
}
