import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The modules read NEXT_PUBLIC_API_URL at import time: stub it, then import a fresh copy.
async function loadHttp() {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
  vi.resetModules();
  return import("./http");
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" }, ...init });
}

const RULE = {
  id: "r_low_stock",
  version: 1,
  status: "active",
  natural_language: "Alerter quand le stock est bas.",
  trigger: { source: "whatsapp", entity: "product" },
  joins: [],
  window_seconds: 604_800,
  emit: { severity: "warning", template: "t" },
  created_at: "2026-11-10T09:00:00",
  updated_at: "2026-11-10T09:00:00",
};

describe("requestJson", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("window", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should return the parsed data when the answer is valid", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ n: 3 }));
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, (data) => (data as { n: number }).n);

    expect(result).toEqual({ ok: true, data: 3 });
  });

  it("should return invalid_response when the parser rejects the body", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, () => undefined);

    expect(result).toEqual({ ok: false, error: { kind: "invalid_response" } });
  });

  it("should return a network error when fetch throws", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("offline"));
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, () => 1);

    expect(result).toEqual({ ok: false, error: { kind: "network" } });
  });

  it("should read the code and Retry-After of a rate limit answer", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: { code: "rate_limit_exceeded", message: "x" } }, { status: 429, headers: { "Retry-After": "30" } }),
    );
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, () => 1);

    expect(result).toEqual({
      ok: false,
      error: { kind: "http", status: 429, code: "rate_limit_exceeded", retryAfterSeconds: 30, fallbackRules: [] },
    });
  });

  it("should keep only valid fallback rules of an nl error", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: { code: "nl_feature_disabled", message: "x", fallback_rules: [RULE, { id: "broken" }] } }, { status: 503 }),
    );
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, () => 1);

    expect(result.ok === false && result.error.kind === "http" && result.error.fallbackRules).toEqual([RULE]);
  });

  it("should leave the code undefined when the detail is a FastAPI validation list", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: [{ loc: ["body"], msg: "bad", type: "x" }] }, { status: 422 }));
    const { requestJson } = await loadHttp();

    const result = await requestJson("/x", {}, () => 1);

    expect(result.ok === false && result.error.kind === "http" && result.error.code).toBeUndefined();
  });
});

describe("requestVoid", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("window", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should succeed on a 204 answer", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    const { requestVoid } = await loadHttp();

    expect(await requestVoid("/x", { method: "DELETE" })).toEqual({ ok: true, data: null });
  });

  it("should fail with the status on a 404 answer", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: { code: "rule_not_found" } }, { status: 404 }));
    const { requestVoid } = await loadHttp();

    const result = await requestVoid("/x", { method: "DELETE" });

    expect(result.ok === false && result.error.kind === "http" && result.error.status).toBe(404);
  });
});
