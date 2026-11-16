"use client";

import { LOCALES, type Locale } from "../lib/i18n";
import { MoonIcon, SunIcon } from "./icons";
import { useI18n } from "./locale-provider";
import { useTheme } from "./theme-provider";

/** Language switcher (FR / EN). Each button names its language in that language. */
export function LocaleSwitcher() {
  const { locale, setLocale, t } = useI18n();
  const names: Record<Locale, string> = { fr: t("locale.fr"), en: t("locale.en") };
  return (
    <div role="group" aria-label={t("locale.label")} className="segmented">
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          lang={code}
          className="segmented-option"
          aria-pressed={locale === code}
          aria-label={names[code]}
          onClick={() => setLocale(code)}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

/** Light/dark switch. The pressed state means "dark theme is on". */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  return (
    <button
      type="button"
      className="button button-secondary icon-button"
      aria-pressed={theme === "dark"}
      aria-label={t("theme.dark")}
      onClick={toggleTheme}
    >
      {theme === "dark" ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}
