"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ACTION_STYLE } from "@/lib/events/labels";
import type { Action, SentinelEvent } from "@/lib/events/types";

// Thresholds mirror the backend's combine() (FLAG >= 0.5, PAUSE >= 0.8).
const FLAG_AT = 0.5;
const PAUSE_AT = 0.8;
const INK = "#52525b";
const GRID = "#e4e4e7";

type Point = { step: number; risk: number; action: Action; tool: string };

function StatusDot(props: { cx?: number; cy?: number; payload?: Point }) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined || !payload) return null;
  // 2px surface ring keeps overlapping markers readable.
  return (
    <circle cx={cx} cy={cy} r={5} fill={ACTION_STYLE[payload.action].color} stroke="#fff" strokeWidth={2} />
  );
}

function RiskTooltip({ active, payload }: TooltipContentProps) {
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-sm">
      <p className="font-medium">
        Step {point.step} · {point.tool}
      </p>
      <p className="text-muted-foreground">
        risk {point.risk.toFixed(2)} · {ACTION_STYLE[point.action].label}
      </p>
    </div>
  );
}

export function RiskChart({ events }: { events: SentinelEvent[] }) {
  const data: Point[] = events.map((e) => ({ step: e.step, risk: e.risk, action: e.action, tool: e.tool }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Risk per step</CardTitle>
        <CardDescription>Above the dashed lines Sentinel flags, then pauses the agent.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-56" role="img" aria-label="Risk score per agent step">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 64, bottom: 0, left: -16 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis
                dataKey="step"
                allowDecimals={false}
                tickLine={false}
                axisLine={{ stroke: GRID }}
                tick={{ fontSize: 12, fill: INK }}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, FLAG_AT, PAUSE_AT, 1]}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12, fill: INK }}
              />
              <ReferenceLine
                y={FLAG_AT}
                stroke={ACTION_STYLE.FLAG.color}
                strokeDasharray="4 4"
                label={{ value: "Flag", position: "right", fontSize: 12, fill: INK }}
              />
              <ReferenceLine
                y={PAUSE_AT}
                stroke={ACTION_STYLE.PAUSE.color}
                strokeDasharray="4 4"
                label={{ value: "Pause", position: "right", fontSize: 12, fill: INK }}
              />
              <Tooltip content={RiskTooltip} cursor={{ stroke: INK, strokeWidth: 1 }} />
              <Line
                type="linear"
                dataKey="risk"
                stroke={INK}
                strokeWidth={2}
                dot={<StatusDot />}
                activeDot={{ r: 7, stroke: "#fff", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
