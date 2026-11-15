/** Backend limits of `POST /api/v1/normalize`: 1 text of 200 characters, 20 comparisons. */
export const SANDBOX_MAX_COMPARISONS = 20;
export const SANDBOX_MAX_TEXT_LENGTH = 200;

/** The same product written four ways in the demo scenario (Roadmap section 2). */
export const CIMENT_VARIANTS: readonly string[] = ["ciment 50 kg", "Ciment50kg", "cimént 50kg", "ciment (50kg)"];

/** Same product, different size: must not match. */
export const CIMENT_SIZES: readonly string[] = ["ciment 50 kg", "ciment 40 kg"];

export type SandboxInput =
  | { ok: true; text: string; compareWith: string[] }
  | { ok: false; reason: "empty" | "too_many" | "too_long" };

/**
 * Turn the textarea content (one text per line) into the request: the first
 * line is the reference text, the other lines are compared with it. Blank
 * lines are dropped.
 */
export function parseSandboxInput(raw: string): SandboxInput {
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
  if (lines.length === 0) {
    return { ok: false, reason: "empty" };
  }
  if (lines.length > SANDBOX_MAX_COMPARISONS + 1) {
    return { ok: false, reason: "too_many" };
  }
  if (lines.some((line) => line.length > SANDBOX_MAX_TEXT_LENGTH)) {
    return { ok: false, reason: "too_long" };
  }
  const [text, ...compareWith] = lines;
  return { ok: true, text, compareWith };
}

/** A similarity in [0, 1] as a localized percentage. */
export function formatScore(score: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(score);
}
