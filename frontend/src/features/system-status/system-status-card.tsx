"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

import { type BackendHealth, useBackendHealth } from "./use-backend-health";

const STATUS_VIEW: Record<BackendHealth["state"], { label: string; dotClass: string; textClass: string }> = {
  checking: { label: "checking…", dotClass: "bg-muted-foreground animate-pulse", textClass: "text-muted-foreground" },
  connected: { label: "connected", dotClass: "bg-green-500", textClass: "text-green-600 dark:text-green-400" },
  disconnected: { label: "disconnected", dotClass: "bg-red-500", textClass: "text-red-600 dark:text-red-400" },
};

export function SystemStatusCard() {
  const health = useBackendHealth();
  const view = STATUS_VIEW[health.state];

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>System Status</CardTitle>
        <CardDescription>Sentinel API at {env.apiUrl}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <p className="flex items-center gap-2 text-sm font-medium" role="status" aria-live="polite">
          <span className={cn("size-2.5 rounded-full", view.dotClass)} aria-hidden />
          <span>Backend:</span>
          <span className={view.textClass}>{view.label}</span>
        </p>
        {health.state === "connected" && <Badge variant="outline">v{health.version}</Badge>}
      </CardContent>
    </Card>
  );
}
