import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api-client";

import { isHealthResponse } from "./schemas";

const POLL_INTERVAL_MS = 5_000;
const REQUEST_TIMEOUT_MS = 3_000;

export type BackendHealth =
  | { state: "checking" }
  | { state: "connected"; version: string }
  | { state: "disconnected" };

/** Polls GET /health so the card recovers on its own when the backend restarts. */
export function useBackendHealth(): BackendHealth {
  const [health, setHealth] = useState<BackendHealth>({ state: "checking" });

  useEffect(() => {
    let active = true;
    let controller: AbortController | null = null;

    async function check(): Promise<void> {
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), REQUEST_TIMEOUT_MS);
      try {
        const body = await apiGet("/health", { signal: controller.signal });
        if (!active) return;
        setHealth(
          isHealthResponse(body)
            ? { state: "connected", version: body.version }
            : { state: "disconnected" },
        );
      } catch {
        if (active) setHealth({ state: "disconnected" });
      } finally {
        clearTimeout(timeout);
      }
    }

    void check();
    const interval = setInterval(() => void check(), POLL_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(interval);
      controller?.abort();
    };
  }, []);

  return health;
}
