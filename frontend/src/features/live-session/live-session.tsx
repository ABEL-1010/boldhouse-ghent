"use client";

import { useState } from "react";

import { ApprovalDialog } from "@/features/approvals";
import { RiskChart } from "@/features/risk-chart";
import { SignalPanel } from "@/features/signals";
import { Timeline } from "@/features/timeline";
import { eventsForSession, pendingDecisions, sessionsOf } from "@/lib/events/store";
import { type Connection, useEventStream } from "@/lib/events/use-event-stream";
import { cn } from "@/lib/utils";

const CONNECTION_VIEW: Record<Connection, { label: string; dot: string }> = {
  connecting: { label: "Connecting to Sentinel…", dot: "bg-muted-foreground animate-pulse" },
  live: { label: "Live", dot: "bg-[#0ca30c]" },
  reconnecting: { label: "Reconnecting…", dot: "bg-[#fab219] animate-pulse" },
};

export function LiveSession() {
  const { store, connection } = useEventStream();
  // Follow the newest session and action unless the user picked one.
  const [pickedSession, setPickedSession] = useState<string | null>(null);
  const [pickedEvent, setPickedEvent] = useState<string | null>(null);

  const sessions = sessionsOf(store);
  const session = pickedSession && sessions.includes(pickedSession) ? pickedSession : sessions.at(-1);
  const events = session ? eventsForSession(store, session) : [];
  const selected = events.find((event) => event.event_id === pickedEvent) ?? events.at(-1);
  const pending = pendingDecisions(store);
  const view = CONNECTION_VIEW[connection];

  return (
    <section className="grid gap-4" aria-label="Live session">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Live session</h2>
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground" role="status">
            <span className={cn("size-2 rounded-full", view.dot)} aria-hidden />
            {view.label}
          </span>
        </div>
        {sessions.length > 0 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Session</span>
            <select
              className="rounded-md border bg-background px-2 py-1 font-mono text-sm"
              value={session}
              onChange={(change) => {
                setPickedSession(change.target.value);
                setPickedEvent(null);
              }}
            >
              {[...sessions].reverse().map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Timeline events={events} selectedId={selected?.event_id} onSelect={setPickedEvent} />
        <div className="grid content-start gap-6">
          <RiskChart events={events} />
          <SignalPanel event={selected} />
        </div>
      </div>

      <ApprovalDialog event={pending[0]} waiting={pending.length} />
    </section>
  );
}
