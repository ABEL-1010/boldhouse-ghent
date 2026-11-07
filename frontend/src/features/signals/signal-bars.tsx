import type { Signals } from "@/lib/events/types";

type Row = { label: string; value: number; detail: string };

function rowsFor(signals: Signals): Row[] {
  const rules = signals.rules.length;
  return [
    {
      label: "Policy rules",
      value: rules > 0 ? 1 : 0,
      detail: rules > 0 ? `${rules} hit` : "none",
    },
    { label: "Taint", value: signals.taint ? 1 : 0, detail: signals.taint ? "leak" : "clean" },
    { label: "ML anomaly", value: signals.ml_risk, detail: signals.ml_risk.toFixed(2) },
    { label: "Sequence", value: signals.markov_risk, detail: signals.markov_risk.toFixed(2) },
  ];
}

/** One neutral hue for magnitude; the status color lives on the action badge, not here. */
export function SignalBars({ signals }: { signals: Signals }) {
  return (
    <dl className="grid gap-2.5">
      {rowsFor(signals).map((row) => (
        <div key={row.label} className="grid grid-cols-[6.5rem_1fr_4.5rem] items-center gap-3 text-sm">
          <dt className="text-muted-foreground">{row.label}</dt>
          <div
            className="h-2 rounded-full bg-muted"
            role="meter"
            aria-label={row.label}
            aria-valuemin={0}
            aria-valuemax={1}
            aria-valuenow={row.value}
          >
            <div
              className="h-full rounded-full bg-foreground/70 transition-[width]"
              style={{ width: `${Math.round(row.value * 100)}%` }}
            />
          </div>
          <dd className="text-right font-mono text-xs tabular-nums">{row.detail}</dd>
        </div>
      ))}
    </dl>
  );
}
