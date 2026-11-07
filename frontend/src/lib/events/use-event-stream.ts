"use client";

import { useEffect, useReducer, useState } from "react";

import { env } from "@/lib/env";

import { isSentinelEvent, STREAM_EVENT_TYPES } from "./guards";
import { applyEvent, emptyStore, type EventStore } from "./store";
import type { SentinelEvent } from "./types";

export type Connection = "connecting" | "live" | "reconnecting";

type StoreAction = { type: "reset" } | { type: "event"; event: SentinelEvent };

function reducer(store: EventStore, action: StoreAction): EventStore {
  return action.type === "reset" ? emptyStore : applyEvent(store, action.event);
}

/** Live Sentinel events over SSE. The server replays its history on every (re)connect. */
export function useEventStream(): { store: EventStore; connection: Connection } {
  const [store, dispatch] = useReducer(reducer, emptyStore);
  const [connection, setConnection] = useState<Connection>("connecting");

  useEffect(() => {
    const source = new EventSource(`${env.apiUrl}/events`);
    const onMessage = (message: MessageEvent<string>) => {
      try {
        const payload: unknown = JSON.parse(message.data);
        if (isSentinelEvent(payload)) dispatch({ type: "event", event: payload });
      } catch {
        // A malformed message is dropped; the next snapshot of that event repairs the state.
      }
    };

    source.onopen = () => {
      // History is replayed after (re)connect, so start from a clean slate to avoid ghosts.
      dispatch({ type: "reset" });
      setConnection("live");
    };
    source.onerror = () => setConnection("reconnecting");
    for (const type of STREAM_EVENT_TYPES) source.addEventListener(type, onMessage);

    return () => source.close();
  }, []);

  return { store, connection };
}
