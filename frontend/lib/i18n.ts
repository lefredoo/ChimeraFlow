import en from "../messages/en.json";
import fr from "../messages/fr.json";

export type Locale = "fr" | "en";
export type MessageKey = keyof typeof fr;

export const LOCALES: readonly Locale[] = ["fr", "en"];
export const DEFAULT_LOCALE: Locale = "fr";

// `satisfies` makes the build fail when a key exists in one language only
// (AGENTS.md section 8: every FR key needs its EN equivalent).
const MESSAGES = {
  fr,
  en: en satisfies Record<MessageKey, string>,
} satisfies Record<Locale, Record<MessageKey, string>>;

export type MessageParams = Record<string, string | number>;

type StripOther<Key> = Key extends `${infer Base}.other` ? Base : never;

/** Base of a plural message: the key without its `.one` / `.other` suffix. */
export type PluralBase = StripOther<MessageKey>;

/** Whether `value` is a supported locale code. */
export function isLocale(value: unknown): value is Locale {
  return value === "fr" || value === "en";
}

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

/**
 * Translate a plural message with the CLDR rules of the locale (`Intl.PluralRules`).
 *
 * The catalogs hold one key per category (`base.one`, `base.other`). The
 * `{count}` placeholder is filled with the number formatted for the locale.
 * A missing category falls back to `base.other`.
 *
 * @param base Plural base key (checked at compile time).
 * @param count Quantity that selects the form.
 * @param params Extra placeholder values.
 * @param locale Language, French by default.
 */
export function tp(
  base: PluralBase,
  count: number,
  params?: MessageParams,
  locale: Locale = DEFAULT_LOCALE,
): string {
  const category = new Intl.PluralRules(locale).select(count);
  const candidate = `${base}.${category}`;
  const key = (Object.prototype.hasOwnProperty.call(MESSAGES[locale], candidate)
    ? candidate
    : `${base}.other`) as MessageKey;
  return t(key, { ...params, count: new Intl.NumberFormat(locale).format(count) }, locale);
}
