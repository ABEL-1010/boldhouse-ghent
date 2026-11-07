import { ApiError, apiPost } from "@/lib/api-client";

// Mirrors the backend rule (gateway MIN_APPROVAL_REASON_CHARS): approving needs a real reason.
export const MIN_APPROVAL_REASON_CHARS = 10;

export async function postDecision(eventId: string, approve: boolean, reason: string): Promise<void> {
  try {
    await apiPost(`/decision/${encodeURIComponent(eventId)}`, { approve, reason });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      throw new ApiError(404, "This action was already decided (or the fail-safe denied it).");
    }
    throw error;
  }
}
