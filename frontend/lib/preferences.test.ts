import { describe, expect, it } from "vitest";

import {
  LOCALE_STORAGE_KEY,
  THEME_STORAGE_KEY,
  loadLocalePreference,
  loadThemePreference,
  resolveTheme,
  saveLocalePreference,
  saveThemePreference,
} from "./preferences";

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  };
}

const blockedStorage = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
};

describe("resolveTheme", () => {
  it("should follow the system when no theme is stored", () => {
    expect(resolveTheme(null, true)).toBe("dark");
  });

  it("should keep the stored theme when the system disagrees", () => {
    expect(resolveTheme("light", true)).toBe("light");
  });
});

describe("locale preference", () => {
  it("should return the stored language when it is supported", () => {
    expect(loadLocalePreference(memoryStorage({ [LOCALE_STORAGE_KEY]: "en" }))).toBe("en");
  });

  it("should return null when the stored language is unknown", () => {
    expect(loadLocalePreference(memoryStorage({ [LOCALE_STORAGE_KEY]: "de" }))).toBeNull();
  });

  it("should return null when storage is blocked", () => {
    expect(loadLocalePreference(blockedStorage)).toBeNull();
  });

  it("should round-trip a saved language", () => {
    const storage = memoryStorage();
    saveLocalePreference(storage, "en");
    expect(loadLocalePreference(storage)).toBe("en");
  });

  it("should not throw when saving to blocked storage", () => {
    expect(() => saveLocalePreference(blockedStorage, "fr")).not.toThrow();
  });
});

describe("theme preference", () => {
  it("should return null when nothing is stored", () => {
    expect(loadThemePreference(memoryStorage())).toBeNull();
  });

  it("should round-trip a saved theme", () => {
    const storage = memoryStorage();
    saveThemePreference(storage, "dark");
    expect(storage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("should ignore an invalid stored theme", () => {
    expect(loadThemePreference(memoryStorage({ [THEME_STORAGE_KEY]: "blue" }))).toBeNull();
  });
});
