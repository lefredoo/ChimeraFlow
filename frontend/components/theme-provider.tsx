"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  getLocalStorage,
  loadThemePreference,
  resolveTheme,
  saveThemePreference,
  type Theme,
  type ThemePreference,
} from "../lib/preferences";

interface ThemeValue {
  /** Theme actually displayed. */
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);
const DARK_QUERY = "(prefers-color-scheme: dark)";

/**
 * Light or dark theme: the stored choice, else the operating system's.
 * The choice is written as `data-theme` on `<html>`, which the CSS tokens read.
 */
export function ThemeProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [preference, setPreference] = useState<ThemePreference>(null);
  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    setPreference(loadThemePreference(getLocalStorage()));
    const query = window.matchMedia(DARK_QUERY);
    setSystemDark(query.matches);
    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const theme = resolveTheme(preference, systemDark);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggleTheme = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setPreference(next);
    saveThemePreference(getLocalStorage(), next);
  }, [theme]);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error("useTheme must be used inside a ThemeProvider");
  }
  return context;
}
