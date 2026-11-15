import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

// The module reads NEXT_PUBLIC_API_URL at import time: stub it, then import.
async function loadFetchHealth() {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
  vi.resetModules();
  return (await import("./health-service")).fetchHealth;
}

describe("fetchHealth", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should return connected with the version when the API answers ok", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok", version: "0.1.0" }));
    const fetchHealth = await loadFetchHealth();

    await expect(fetchHealth()).resolves.toEqual({ state: "connected", version: "0.1.0" });
    expect(fetchMock).toHaveBeenCalledWith("http://api.test/health");
  });

  it("should return error when the status is not ok", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ status: "degraded" }));
    const fetchHealth = await loadFetchHealth();

    await expect(fetchHealth()).resolves.toEqual({ state: "error" });
  });

  it("should return error when the HTTP status is not successful", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 503));
    const fetchHealth = await loadFetchHealth();

    await expect(fetchHealth()).resolves.toEqual({ state: "error" });
  });

  it("should return unreachable when the request fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));
    const fetchHealth = await loadFetchHealth();

    await expect(fetchHealth()).resolves.toEqual({ state: "unreachable" });
  });
});
