import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

class FakeStorage implements Storage {
  private readonly data = new Map<string, string>();

  get length(): number {
    return this.data.size;
  }

  clear(): void {
    this.data.clear();
  }

  getItem(key: string): string | null {
    return this.data.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.data.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.data.delete(key);
  }

  setItem(key: string, value: string): void {
    this.data.set(key, value);
  }
}

const SESSION = { token: "tok", email: "demo@example.test", expiresAt: 10_000 };

// The module keeps the in-memory session at module level: a fresh import is a fresh tab.
async function loadStorageModule() {
  vi.resetModules();
  return import("./token-storage");
}

describe("token storage", () => {
  let sessionStorage: FakeStorage;
  let localStorage: FakeStorage;

  beforeEach(() => {
    sessionStorage = new FakeStorage();
    localStorage = new FakeStorage();
    vi.stubGlobal("window", { sessionStorage, localStorage });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("should return null when no session was saved", async () => {
    const { loadSession } = await loadStorageModule();

    expect(loadSession(0)).toBeNull();
  });

  it("should return the session when it has not expired", async () => {
    const { loadSession, saveSession } = await loadStorageModule();
    saveSession(SESSION);

    expect(loadSession(9_999)).toEqual(SESSION);
  });

  it("should return null when the session has expired", async () => {
    const { loadSession, saveSession } = await loadStorageModule();
    saveSession(SESSION);

    expect(loadSession(10_000)).toBeNull();
  });

  it("should remove the session from the storage when it has expired", async () => {
    const { SESSION_STORAGE_KEY, loadSession, saveSession } = await loadStorageModule();
    saveSession(SESSION);

    loadSession(10_000);

    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("should restore the session when the page is reloaded", async () => {
    const first = await loadStorageModule();
    first.saveSession(SESSION);

    const { loadSession } = await loadStorageModule();

    expect(loadSession(0)).toEqual(SESSION);
  });

  it("should forget the session when it is cleared", async () => {
    const { clearSession, loadSession, saveSession } = await loadStorageModule();
    saveSession(SESSION);

    clearSession();

    expect(loadSession(0)).toBeNull();
  });

  it("should forget the session after a reload when it was cleared", async () => {
    const first = await loadStorageModule();
    first.saveSession(SESSION);
    first.clearSession();

    const { loadSession } = await loadStorageModule();

    expect(loadSession(0)).toBeNull();
  });

  it("should never write the token to localStorage when saving a session", async () => {
    const { saveSession } = await loadStorageModule();

    saveSession(SESSION);

    expect(localStorage.length).toBe(0);
  });

  it("should return null when the stored value is not JSON", async () => {
    const { SESSION_STORAGE_KEY, loadSession } = await loadStorageModule();
    sessionStorage.setItem(SESSION_STORAGE_KEY, "{not json");

    expect(loadSession(0)).toBeNull();
  });

  it("should return null when the stored value has the wrong shape", async () => {
    const { SESSION_STORAGE_KEY, loadSession } = await loadStorageModule();
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ token: 1, email: "a", expiresAt: "x" }));

    expect(loadSession(0)).toBeNull();
  });

  it("should keep the session in memory when sessionStorage is blocked", async () => {
    vi.stubGlobal("window", {
      get sessionStorage(): Storage {
        throw new DOMException("denied", "SecurityError");
      },
    });
    const { loadSession, saveSession } = await loadStorageModule();

    saveSession(SESSION);

    expect(loadSession(0)).toEqual(SESSION);
  });

  it("should keep the session in memory when there is no window", async () => {
    vi.stubGlobal("window", undefined);
    const { loadSession, saveSession } = await loadStorageModule();

    saveSession(SESSION);

    expect(loadSession(0)).toEqual(SESSION);
  });
});
