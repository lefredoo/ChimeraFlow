import { isLocale, type Locale } from "./i18n";

/**
 * UI preferences (language, theme). They are not secrets, so `localStorage`
 * is fine here; the access token never goes there (see auth/token-storage.ts).
 */
export const LOCALE_STORAGE_KEY = "chimeraflow.locale";
export const THEME_STORAGE_KEY = "chimeraflow.theme";

export type Theme = "light" | "dark";

/** `null` means "follow the operating system". */
export type ThemePreference = Theme | null;

export function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

/** Theme actually displayed for a preference and the OS setting. */
export function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): Theme {
  if (preference !== null) {
    return preference;
  }
  return systemPrefersDark ? "dark" : "light";
}

function readItem(storage: Pick<Storage, "getItem"> | null, key: string): string | null {
  if (storage === null) {
    return null;
  }
  try {
    return storage.getItem(key);
  } catch {
    // Blocked storage (private mode, policy): the preference is just not remembered
    return null;
  }
}

function writeItem(storage: Pick<Storage, "setItem"> | null, key: string, value: string): void {
  if (storage === null) {
    return;
  }
  try {
    storage.setItem(key, value);
  } catch {
    // Same as above: a refused write must not break the page
  }
}

/** Stored language, or null when none is stored or the value is unknown. */
export function loadLocalePreference(storage: Pick<Storage, "getItem"> | null): Locale | null {
  const raw = readItem(storage, LOCALE_STORAGE_KEY);
  return isLocale(raw) ? raw : null;
}

export function saveLocalePreference(storage: Pick<Storage, "setItem"> | null, locale: Locale): void {
  writeItem(storage, LOCALE_STORAGE_KEY, locale);
}

/** Stored theme, or null (follow the system) when none is stored or the value is unknown. */
export function loadThemePreference(storage: Pick<Storage, "getItem"> | null): ThemePreference {
  const raw = readItem(storage, THEME_STORAGE_KEY);
  return isTheme(raw) ? raw : null;
}

export function saveThemePreference(storage: Pick<Storage, "setItem"> | null, theme: Theme): void {
  writeItem(storage, THEME_STORAGE_KEY, theme);
}

/** The browser's `localStorage`, or null on the server or when access throws. */
export function getLocalStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
