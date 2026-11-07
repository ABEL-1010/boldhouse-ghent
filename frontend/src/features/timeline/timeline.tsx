import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ActionBadge } from "@/lib/events/action-badge";
import { ACTION_STYLE, targetOf } from "@/lib/events/labels";
import { type Outcome, outcomeOf } from "@/lib/events/store";
import type { SentinelEvent } from "@/lib/events/types";
import { cn } from "@/lib/utils";

const OUTCOME_LABEL: Record<Outcome, string> = {
  "awaiting-human": "Waiting for a human",
  running: "Running",
  executed: "Executed",
  blocked: "Blocked",
  failed: "Failed",
};

type TimelineProps = {
  events: SentinelEvent[];
  selectedId: string | undefined;
  onSelect: (eventId: string) => void;
};

export function Timeline({ events, selectedId, onSelect }: TimelineProps) {
  return (
    <Card className="min-h-0">
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
        <CardDescription>Every tool call the agent made, in order.</CardDescription>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No actions yet. Start an agent run.</p>
        ) : (
          <ol className="grid gap-2" aria-label="Agent actions">
            {events.map((event) => (
              <li key={event.event_id}>
                <TimelineCard
                  event={event}
                  selected={event.event_id === selectedId}
                  onSelect={() => onSelect(event.event_id)}
                />
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

function TimelineCard({
  event,
  selected,
  onSelect,
}: {
  event: SentinelEvent;
  selected: boolean;
  onSelect: () => void;
}) {
  const outcome = outcomeOf(event);
  // Show who decided and why: the human's reason is the accountability trail.
  const decision = event.decision;
  const label =
    outcome === "executed" && decision?.approve ? "Approved by human, executed" : OUTCOME_LABEL[outcome];
  const reason = decision && (outcome === "blocked" || decision.approve) ? decision.reason : undefined;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "w-full rounded-lg border border-l-4 bg-card p-3 text-left transition-colors hover:bg-muted/50",
        ACTION_STYLE[event.action].borderClass,
        selected && "ring-2 ring-ring/40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-sm font-medium">
          <span className="text-muted-foreground">{event.step}.</span> {event.tool}
        </span>
        <ActionBadge action={event.action} />
      </div>
      <p className="mt-1 truncate font-mono text-xs text-muted-foreground" title={targetOf(event)}>
        {targetOf(event) || "(no target)"}
      </p>
      <div className="mt-2 flex items-start justify-between gap-3 text-xs">
        <span className={cn("min-w-0", outcome === "awaiting-human" && "font-medium text-[#a32626]")}>
          {label}
          {reason && <span className="text-muted-foreground">: {reason}</span>}
        </span>
        <span className="shrink-0 font-mono whitespace-nowrap tabular-nums text-muted-foreground">
          risk {event.risk.toFixed(2)}
        </span>
      </div>
    </button>
  );
}
