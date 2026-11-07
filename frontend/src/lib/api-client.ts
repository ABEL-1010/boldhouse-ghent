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

/** GET a JSON resource from the Sentinel API. Callers validate the returned shape. */
export async function apiGet(path: string, init?: { signal?: AbortSignal }): Promise<unknown> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal: init?.signal,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with ${response.status}`);
  }
  return response.json();
}
