import { env } from "@/lib/env";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function errorFrom(response: Response, fallback: string): Promise<ApiError> {
  // FastAPI puts the human-readable reason in {"detail": "..."}.
  const body: unknown = await response.json().catch(() => null);
  const detail =
    typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string"
      ? body.detail
      : fallback;
  return new ApiError(response.status, detail);
}

/** GET a JSON resource from the Sentinel API. Callers validate the returned shape. */
export async function apiGet(path: string, init?: { signal?: AbortSignal }): Promise<unknown> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal: init?.signal,
  });
  if (!response.ok) {
    throw await errorFrom(response, `GET ${path} failed with ${response.status}`);
  }
  return response.json();
}

/** POST JSON to the Sentinel API. Callers validate the returned shape. */
export async function apiPost(path: string, body: unknown): Promise<unknown> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await errorFrom(response, `POST ${path} failed with ${response.status}`);
  }
  return response.json();
}
