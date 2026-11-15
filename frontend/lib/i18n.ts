import en from "../messages/en.json";
import fr from "../messages/fr.json";

export type Locale = "fr" | "en";
export type MessageKey = keyof typeof fr;

export const DEFAULT_LOCALE: Locale = "fr";

// `satisfies` makes the build fail when a key exists in one language only
// (AGENTS.md section 8: every FR key needs its EN equivalent).
const MESSAGES = {
  fr,
  en: en satisfies Record<MessageKey, string>,
} satisfies Record<Locale, Record<MessageKey, string>>;

export type MessageParams = Record<string, string | number>;

/**
 * Translate a key, replacing `{name}` placeholders with `params` values.
 *
 * Placeholders without a matching param are left as is, so a missing value is
 * visible instead of silently dropped.
 *
 * @param key Message key (checked at compile time).
 * @param params Placeholder values.
 * @param locale Language, French by default.
 */
export function t(key: MessageKey, params?: MessageParams, locale: Locale = DEFAULT_LOCALE): string {
  const message: string = MESSAGES[locale][key];
  if (params === undefined) {
    return message;
  }
  return message.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder,
  );
}
