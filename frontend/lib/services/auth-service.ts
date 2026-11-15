import { API_URL } from "../config";
import type { Session } from "../auth/token-storage";
import { apiFetch } from "./api-client";

export type LoginResult =
  | { state: "success"; session: Session }
  | { state: "invalid_credentials" }
  | { state: "rate_limited"; retryAfterSeconds: number | undefined }
  | { state: "unreachable" }
  | { state: "error" };

export type CurrentUserResult =
  | { state: "authenticated"; email: string }
  | { state: "unauthorized" }
  | { state: "unreachable" }
  | { state: "error" };

interface TokenPayload {
  access_token: string;
  expires_in: number;
}

function isTokenPayload(data: unknown): data is TokenPayload {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const { access_token: token, expires_in: expiresIn } = data as Record<string, unknown>;
  return typeof token === "string" && token !== "" && typeof expiresIn === "number" && expiresIn > 0;
}

function parseRetryAfter(header: string | null): number | undefined {
  if (header === null) {
    return undefined;
  }
  const seconds = Number.parseInt(header, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined;
}

/**
 * Exchange the credentials for a session.
 *
 * Failures are not thrown: they become the states the login form displays.
 * This call does not use `apiFetch`: a 401 here means wrong credentials, not
 * an expired session.
 *
 * @param email Account email.
 * @param password Account password.
 * @param now Current time in epoch milliseconds (to compute the expiry).
 */
export async function login(email: string, password: string, now: number = Date.now()): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return { state: "unreachable" };
  }
  if (response.status === 401) {
    return { state: "invalid_credentials" };
  }
  if (response.status === 429) {
    return { state: "rate_limited", retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")) };
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
  if (!isTokenPayload(data)) {
    return { state: "error" };
  }
  return {
    state: "success",
    session: {
      token: data.access_token,
      email: email.trim().toLowerCase(),
      expiresAt: now + data.expires_in * 1000,
    },
  };
}

/**
 * Ask the API which account the stored token belongs to.
 *
 * A 401 is reported as `unauthorized` (the session is already dropped by
 * `apiFetch`); network and server failures are other states, so a flaky
 * network does not log the user out.
 */
export async function fetchCurrentUser(): Promise<CurrentUserResult> {
  let response: Response;
  try {
    response = await apiFetch("/api/v1/auth/me");
  } catch {
    return { state: "unreachable" };
  }
  if (response.status === 401) {
    return { state: "unauthorized" };
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
  const email = typeof data === "object" && data !== null ? (data as Record<string, unknown>).email : undefined;
  return typeof email === "string" ? { state: "authenticated", email } : { state: "error" };
}
