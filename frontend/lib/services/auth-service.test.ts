import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

async function loadModules() {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
  vi.resetModules();
  const storage = await import("../auth/token-storage");
  const service = await import("./auth-service");
  return { ...storage, ...service };
}

describe("login", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("window", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should return a session expiring after expires_in when the credentials are accepted", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ access_token: "tok", token_type: "bearer", expires_in: 3600 }),
    );
    const { login } = await loadModules();

    await expect(login("  Demo@Example.test ", "pw", 1_000)).resolves.toEqual({
      state: "success",
      session: { token: "tok", email: "demo@example.test", expiresAt: 3_601_000 },
    });
  });

  it("should post the credentials as JSON when logging in", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "tok", expires_in: 3600 }));
    const { login } = await loadModules();

    await login("demo@example.test", "pw");

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect([url, init?.method, init?.body]).toEqual([
      "http://api.test/api/v1/auth/login",
      "POST",
      JSON.stringify({ email: "demo@example.test", password: "pw" }),
    ]);
  });

  it("should send no Authorization header when logging in", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "tok", expires_in: 3600 }));
    const { login, saveSession } = await loadModules();
    saveSession({ token: "old", email: "a@b.test", expiresAt: Date.now() + 60_000 });

    await login("demo@example.test", "pw");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("should return invalid_credentials when the API answers 401", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: { code: "auth_invalid_credentials", message: "Invalid credentials" } }, 401),
    );
    const { login } = await loadModules();

    await expect(login("demo@example.test", "bad")).resolves.toEqual({ state: "invalid_credentials" });
  });

  it("should not drop the stored session when the credentials are refused", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 401));
    const { login, loadSession, saveSession } = await loadModules();
    const session = { token: "old", email: "a@b.test", expiresAt: Date.now() + 60_000 };
    saveSession(session);

    await login("demo@example.test", "bad");

    expect(loadSession()).toEqual(session);
  });

  it("should return the retry delay when the API answers 429 with Retry-After", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 429, { "Retry-After": "42" }));
    const { login } = await loadModules();

    await expect(login("demo@example.test", "pw")).resolves.toEqual({
      state: "rate_limited",
      retryAfterSeconds: 42,
    });
  });

  it("should return no retry delay when the API answers 429 without a readable Retry-After", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 429));
    const { login } = await loadModules();

    await expect(login("demo@example.test", "pw")).resolves.toEqual({
      state: "rate_limited",
      retryAfterSeconds: undefined,
    });
  });

  it("should return error when the API answers 500", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 500));
    const { login } = await loadModules();

    await expect(login("demo@example.test", "pw")).resolves.toEqual({ state: "error" });
  });

  it("should return error when the token payload is malformed", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: 5 }));
    const { login } = await loadModules();

    await expect(login("demo@example.test", "pw")).resolves.toEqual({ state: "error" });
  });

  it("should return unreachable when the request fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));
    const { login } = await loadModules();

    await expect(login("demo@example.test", "pw")).resolves.toEqual({ state: "unreachable" });
  });
});

describe("fetchCurrentUser", () => {
  const SESSION = { token: "tok-123", email: "demo@example.test", expiresAt: Date.now() + 60_000 };

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("window", undefined);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("should return the account email when the token is accepted", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ email: "demo@example.test" }));
    const { fetchCurrentUser, saveSession } = await loadModules();
    saveSession(SESSION);

    await expect(fetchCurrentUser()).resolves.toEqual({ state: "authenticated", email: "demo@example.test" });
  });

  it("should send the Bearer token when asking for the account", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ email: "demo@example.test" }));
    const { fetchCurrentUser, saveSession } = await loadModules();
    saveSession(SESSION);

    await fetchCurrentUser();

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect([url, new Headers(init?.headers).get("Authorization")]).toEqual([
      "http://api.test/api/v1/auth/me",
      "Bearer tok-123",
    ]);
  });

  it("should return unauthorized and drop the session when the API answers 401", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: { code: "auth_token_expired", message: "Token expired" } }, 401),
    );
    const { fetchCurrentUser, loadSession, saveSession } = await loadModules();
    saveSession(SESSION);

    const result = await fetchCurrentUser();

    expect([result, loadSession()]).toEqual([{ state: "unauthorized" }, null]);
  });

  it("should return unreachable and keep the session when the request fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network down"));
    const { fetchCurrentUser, loadSession, saveSession } = await loadModules();
    saveSession(SESSION);

    const result = await fetchCurrentUser();

    expect([result, loadSession()]).toEqual([{ state: "unreachable" }, SESSION]);
  });

  it("should return error when the API answers 503", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}, 503));
    const { fetchCurrentUser } = await loadModules();

    await expect(fetchCurrentUser()).resolves.toEqual({ state: "error" });
  });
});
