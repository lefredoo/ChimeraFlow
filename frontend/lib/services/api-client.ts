import { API_URL } from "../config";
import { clearSession, loadSession } from "../auth/token-storage";

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/**
 * Register the function called when the API refuses the session (401).
 * Pass null to unregister.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

/**
 * `fetch` on the backend API with the session token as Bearer header.
 *
 * A 401 answer means the token is expired or invalid: the session is dropped
 * and the registered handler runs (the UI goes back to the login page). The
 * response is still returned to the caller.
 *
 * Network failures are thrown by `fetch` and left to the caller.
 *
 * @param path API path starting with `/`.
 * @param init Request options.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const session = loadSession();
  if (session !== null) {
    headers.set("Authorization", `Bearer ${session.token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    unauthorizedHandler?.();
  }
  return response;
}
