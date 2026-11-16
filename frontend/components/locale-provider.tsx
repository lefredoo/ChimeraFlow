"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  DEFAULT_LOCALE,
  t as translate,
  tp as translatePlural,
  type Locale,
  type MessageKey,
  type MessageParams,
  type PluralBase,
} from "../lib/i18n";
import { getLocalStorage, loadLocalePreference, saveLocalePreference } from "../lib/preferences";

interface I18nValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, params?: MessageParams) => string;
  tp: (base: PluralBase, count: number, params?: MessageParams) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

/** Current language (French by default, then the stored choice) for the whole tree. */
export function LocaleProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  // The server render and the first client render use the default language
  // so hydration matches; the stored choice is applied right after.
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = loadLocalePreference(getLocalStorage());
    if (stored !== null) {
      setLocaleState(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = translate("meta.title", undefined, locale);
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    saveLocalePreference(getLocalStorage(), next);
  }, []);

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      setLocale,
      t: (key, params) => translate(key, params, locale),
      tp: (base, count, params) => translatePlural(base, count, params, locale),
    }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext);
  if (context === null) {
    throw new Error("useI18n must be used inside a LocaleProvider");
  }
  return context;
}
