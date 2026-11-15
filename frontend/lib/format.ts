import type { Locale } from "./i18n";

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

function parseTime(iso: string): number | null {
  const time = Date.parse(iso);
  return Number.isNaN(time) ? null : time;
}

/**
 * Relative time ("il y a 5 minutes", "in 2 days") with `Intl.RelativeTimeFormat`.
 *
 * @param iso ISO 8601 date string.
 * @param now Current time in epoch milliseconds.
 * @param locale Display language.
 * @returns The text, or null when `iso` is not a valid date.
 */
export function formatRelativeTime(iso: string, now: number, locale: Locale): string | null {
  const time = parseTime(iso);
  if (time === null) {
    return null;
  }
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const diff = time - now;
  const abs = Math.abs(diff);
  if (abs < MINUTE) {
    return formatter.format(Math.round(diff / SECOND), "second");
  }
  if (abs < HOUR) {
    return formatter.format(Math.round(diff / MINUTE), "minute");
  }
  if (abs < DAY) {
    return formatter.format(Math.round(diff / HOUR), "hour");
  }
  return formatter.format(Math.round(diff / DAY), "day");
}

/** Absolute date and time for the locale, or null when `iso` is not a valid date. */
export function formatDateTime(iso: string, locale: Locale): string | null {
  const time = parseTime(iso);
  if (time === null) {
    return null;
  }
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(time);
}

/** "A, B and C" with the conjunction of the locale. */
export function formatList(items: readonly string[], locale: Locale): string {
  return new Intl.ListFormat(locale, { style: "long", type: "conjunction" }).format(items);
}

/** Integer with the thousands separator of the locale. */
export function formatNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale).format(value);
}

/** Duration in a readable unit (ms, then seconds), localized. */
export function formatDuration(milliseconds: number, locale: Locale): string {
  if (milliseconds < SECOND) {
    return new Intl.NumberFormat(locale, { style: "unit", unit: "millisecond", unitDisplay: "short" }).format(
      milliseconds,
    );
  }
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: "second",
    unitDisplay: "short",
    maximumFractionDigits: 1,
  }).format(milliseconds / SECOND);
}

/** A duration given in seconds as the largest whole unit (days, hours, minutes), localized. */
export function formatWindow(seconds: number, locale: Locale): string {
  const units: ReadonlyArray<readonly [Intl.NumberFormatOptions["unit"], number]> = [
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (seconds >= size && seconds % size === 0) {
      return new Intl.NumberFormat(locale, { style: "unit", unit, unitDisplay: "long" }).format(seconds / size);
    }
  }
  return new Intl.NumberFormat(locale, { style: "unit", unit: "second", unitDisplay: "long" }).format(seconds);
}
