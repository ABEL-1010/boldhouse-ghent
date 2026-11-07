import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { reasonsFor, targetOf } from "@/lib/events/labels";
import type { SentinelEvent } from "@/lib/events/types";

import { SignalBars } from "./signal-bars";

export function SignalPanel({ event }: { event: SentinelEvent | undefined }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Signal breakdown</CardTitle>
        <CardDescription>
          {event
            ? `Step ${event.step} · ${event.tool} ${targetOf(event)} · risk ${event.risk.toFixed(2)}`
            : "Select an action in the timeline."}
        </CardDescription>
      </CardHeader>
      {event && (
        <CardContent className="grid gap-4">
          <SignalBars signals={event.signals} />
          <ReasonList event={event} />
        </CardContent>
      )}
    </Card>
  );
}

export function ReasonList({ event }: { event: SentinelEvent }) {
  const reasons = reasonsFor(event);
  if (reasons.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing unusual about this action.</p>;
  }
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  );
}
