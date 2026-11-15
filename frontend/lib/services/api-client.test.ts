import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The modules read NEXT_PUBLIC_API_URL at import time, and the session lives at
// module level: stub the variable, then import a fresh copy.
async function loadModules() {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
  vi.resetModules();
  const storage = await import("../auth/token-storage");
  const client = await import("./api-client");
  return { ...storage, ...client };
}

const SESSION = { token: "tok-123", email: "demo@example.test", expiresAt: Date.now() + 60_000 };

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("window", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should send the session token as a Bearer header when a session exists", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 200 }));
    const { apiFetch, saveSession } = await loadModules();
    saveSession(SESSION);

    await apiFetch("/api/v1/rules");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect([url, new Headers(init?.headers).get("Authorization")]).toEqual([
      "http://api.test/api/v1/rules",
      "Bearer tok-123",
    ]);
  });

  it("should send no Authorization header when there is no session", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 200 }));
    const { apiFetch } = await loadModules();

    await apiFetch("/api/v1/rules");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("should keep the caller's headers and method when adding the token", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 200 }));
    const { apiFetch, saveSession } = await loadModules();
    saveSession(SESSION);

    await apiFetch("/api/v1/rules", { method: "POST", headers: { "Content-Type": "application/json" } });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect([init?.method, new Headers(init?.headers).get("Content-Type")]).toEqual(["POST", "application/json"]);
  });

  it("should drop the session when the API answers 401", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 401 }));
    const { apiFetch, loadSession, saveSession } = await loadModules();
    saveSession(SESSION);

    await apiFetch("/api/v1/rules");

    expect(loadSession()).toBeNull();
  });

  it("should call the unauthorized handler when the API answers 401", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 401 }));
    const { apiFetch, setUnauthorizedHandler } = await loadModules();
    const handler = vi.fn();
    setUnauthorizedHandler(handler);

    await apiFetch("/api/v1/rules");

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("should keep the session when the API answers 500", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("{}", { status: 500 }));
    const { apiFetch, loadSession, saveSession } = await loadModules();
    saveSession(SESSION);

    await apiFetch("/api/v1/rules");

    expect(loadSession()).toEqual(SESSION);
  });
});
