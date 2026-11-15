/**
 * Session storage of the access token.
 *
 * The session lives in memory and is mirrored in `sessionStorage`, so it
 * survives a page reload but not the closing of the tab. It is never put in
 * `localStorage` (shared by every tab, persists after the browser closes) nor
 * in a cookie (the frontend and the API are on different sites: a cookie would
 * be cross-site, blocked by browsers and open to CSRF).
 */

export interface Session {
  /** Bearer token returned by the login endpoint. */
  token: string;
  /** Account email, for display. */
  email: string;
  /** Expiry as epoch milliseconds. */
  expiresAt: number;
}

export const SESSION_STORAGE_KEY = "chimeraflow.session";

let memorySession: Session | null = null;

/** The tab's storage, or null where it is unavailable (server render, blocked storage). */
function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    // Access denied (privacy settings): the session then lives in memory only
    return null;
  }
}

function isSession(data: unknown): data is Session {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const { token, email, expiresAt } = data as Record<string, unknown>;
  return (
    typeof token === "string" &&
    token !== "" &&
    typeof email === "string" &&
    typeof expiresAt === "number" &&
    Number.isFinite(expiresAt)
  );
}

function readStoredSession(storage: Storage): Session | null {
  const raw = storage.getItem(SESSION_STORAGE_KEY);
  if (raw === null) {
    return null;
  }
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  return isSession(data) ? data : null;
}

/**
 * Keep a session in memory and in the tab's storage.
 *
 * @param session Session to keep.
 */
export function saveSession(session: Session): void {
  memorySession = session;
  getStorage()?.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

/** Forget the session everywhere. */
export function clearSession(): void {
  memorySession = null;
  getStorage()?.removeItem(SESSION_STORAGE_KEY);
}

/**
 * Return the current session, or null when there is none or it has expired
 * (an expired session is removed).
 *
 * @param now Current time in epoch milliseconds.
 */
export function loadSession(now: number = Date.now()): Session | null {
  const storage = getStorage();
  const session = memorySession ?? (storage === null ? null : readStoredSession(storage));
  if (session === null) {
    return null;
  }
  if (session.expiresAt <= now) {
    clearSession();
    return null;
  }
  memorySession = session;
  return session;
}
