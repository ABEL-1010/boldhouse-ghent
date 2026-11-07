"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { SignalBars, ReasonList } from "@/features/signals";
import { ActionBadge } from "@/lib/events/action-badge";
import { targetOf } from "@/lib/events/labels";
import type { SentinelEvent } from "@/lib/events/types";

import { MIN_APPROVAL_REASON_CHARS, postDecision } from "./decide";

type ApprovalDialogProps = {
  /** The oldest paused action waiting for a human, if any. */
  event: SentinelEvent | undefined;
  waiting: number;
};

/** Opens automatically on PAUSE and closes when the decision event arrives (human or fail-safe). */
export function ApprovalDialog({ event, waiting }: ApprovalDialogProps) {
  return (
    // No dismissal without a decision: the agent is frozen until a human (or the fail-safe) decides.
    <Dialog open={event !== undefined} onOpenChange={() => undefined}>
      {event && (
        <DialogContent className="sm:max-w-xl" showCloseButton={false}>
          <DecisionForm key={event.event_id} event={event} waiting={waiting} />
        </DialogContent>
      )}
    </Dialog>
  );
}

function DecisionForm({ event, waiting }: { event: SentinelEvent; waiting: number }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reasonOk = reason.trim().length >= MIN_APPROVAL_REASON_CHARS;

  async function decide(approve: boolean) {
    setSubmitting(true);
    setError(null);
    try {
      await postDecision(event.event_id, approve, reason.trim());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send the decision.");
      setSubmitting(false);
    }
  }

  return (
    <>
      <DialogHeader>
        <div className="flex items-center gap-2">
          <ActionBadge action={event.action} />
          <span className="font-mono text-xs text-muted-foreground">
            {event.session_id} · step {event.step} · risk {event.risk.toFixed(2)}
          </span>
        </div>
        <DialogTitle>Sentinel paused the agent</DialogTitle>
        <DialogDescription>
          The agent wants to run <span className="font-mono">{event.tool}</span> on{" "}
          <span className="font-mono break-all">{targetOf(event) || "(no target)"}</span>. Nothing
          runs until you decide.
        </DialogDescription>
      </DialogHeader>

      <pre className="max-h-36 overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap break-all">
        {JSON.stringify(event.args, null, 2)}
      </pre>

      <section className="grid gap-3" aria-label="Why it was paused">
        <SignalBars signals={event.signals} />
        <ReasonList event={event} />
      </section>

      {event.explanation && (
        <section className="rounded-md border p-3 text-sm" aria-label="Claude's explanation">
          <p className="font-medium">Claude&apos;s assessment: {event.explanation.verdict}</p>
          <p className="mt-1">{event.explanation.explanation}</p>
          <p className="mt-1 text-muted-foreground">Check: {event.explanation.what_to_check}</p>
        </section>
      )}

      <label className="grid gap-1.5 text-sm">
        <span>
          Your reason <span className="text-muted-foreground">(required to approve, at least {MIN_APPROVAL_REASON_CHARS} characters)</span>
        </span>
        <Textarea
          value={reason}
          onChange={(change) => setReason(change.target.value)}
          placeholder="Why is this action OK, or why not?"
          rows={3}
          disabled={submitting}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <DialogFooter className="items-center sm:justify-between">
        <p className="text-xs text-muted-foreground">
          No answer means deny (fail-safe).{waiting > 1 && ` ${waiting - 1} more waiting.`}
        </p>
        <div className="flex gap-2">
          <Button variant="destructive" disabled={submitting} onClick={() => decide(false)}>
            Deny
          </Button>
          <Button disabled={submitting || !reasonOk} onClick={() => decide(true)}>
            Approve once
          </Button>
        </div>
      </DialogFooter>
    </>
  );
}
