import type { Rule } from "../api-types";
import { isRule } from "../parsers";
import { apiFetch } from "./api-client";

/** Why a call failed, as data the UI maps to a message (never thrown). */
export type ApiError =
  | { kind: "network" }
  | { kind: "invalid_response" }
  | {
      kind: "http";
      status: number;
      /** Stable error code of the API (`detail.code`), when the body has one. */
      code: string | undefined;
      retryAfterSeconds: number | undefined;
      /** Predefined rules offered when the natural-language conversion is unavailable. */
      fallbackRules: Rule[];
    };

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

function parseRetryAfter(header: string | null): number | undefined {
  if (header === null) {
    return undefined;
  }
  const seconds = Number.parseInt(header, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

async function toHttpError(response: Response): Promise<ApiError> {
  const body = await readJson(response);
  let code: string | undefined;
  let fallbackRules: Rule[] = [];
  if (typeof body === "object" && body !== null) {
    const detail = (body as Record<string, unknown>).detail;
    if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
      const record = detail as Record<string, unknown>;
      code = typeof record.code === "string" ? record.code : undefined;
      fallbackRules = Array.isArray(record.fallback_rules) ? record.fallback_rules.filter(isRule) : [];
    }
  }
  return {
    kind: "http",
    status: response.status,
    code,
    retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")),
    fallbackRules,
  };
}

/**
 * Call the API and parse the JSON answer.
 *
 * @param path API path starting with `/`.
 * @param init Request options.
 * @param parse Narrows the JSON to `T`; returns undefined when the shape is wrong.
 */
export async function requestJson<T>(
  path: string,
  init: RequestInit,
  parse: (data: unknown) => T | undefined,
): Promise<ApiResult<T>> {
  let response: Response;
  try {
    response = await apiFetch(path, init);
  } catch {
    return { ok: false, error: { kind: "network" } };
  }
  if (!response.ok) {
    return { ok: false, error: await toHttpError(response) };
  }
  const parsed = parse(await readJson(response));
  return parsed === undefined ? { ok: false, error: { kind: "invalid_response" } } : { ok: true, data: parsed };
}

/** Call the API for an endpoint without response body (204). */
export async function requestVoid(path: string, init: RequestInit): Promise<ApiResult<null>> {
  let response: Response;
  try {
    response = await apiFetch(path, init);
  } catch {
    return { ok: false, error: { kind: "network" } };
  }
  return response.ok ? { ok: true, data: null } : { ok: false, error: await toHttpError(response) };
}

/** `RequestInit` for a JSON body. */
export function jsonBody(method: "POST" | "PUT", body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
