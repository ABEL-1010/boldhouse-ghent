export type HealthResponse = {
  status: "ok";
  service: "sentinel";
  version: string;
};

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    candidate.status === "ok" &&
    candidate.service === "sentinel" &&
    typeof candidate.version === "string"
  );
}
