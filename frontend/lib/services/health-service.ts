import { API_URL } from "../config";

export type HealthResult =
  | { state: "connected"; version: string | undefined }
  | { state: "error" }
  | { state: "unreachable" };

interface HealthPayload {
  status: string;
  version?: string;
}

function isHealthPayload(data: unknown): data is HealthPayload {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const { status, version } = data as Record<string, unknown>;
  return typeof status === "string" && (version === undefined || typeof version === "string");
}

/**
 * Query the backend `/health` endpoint.
 *
 * Network failures and non-JSON answers are not thrown: they become the
 * `unreachable` and `error` states that the UI displays.
 */
export async function fetchHealth(): Promise<HealthResult> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/health`);
  } catch {
    return { state: "unreachable" };
  }
  if (!response.ok) {
    return { state: "error" };
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    return { state: "error" };
  }
  if (isHealthPayload(data) && data.status === "ok") {
    return { state: "connected", version: data.version };
  }
  return { state: "error" };
}
