export const COMPOSER_MIN_LENGTH = 20;
export const COMPOSER_MAX_LENGTH = 1000;

export type ComposerValidation = "ok" | "too_short" | "too_long";

/** The API trims the text, then requires 20 to 1000 characters. */
export function validateComposerText(text: string): ComposerValidation {
  const length = text.trim().length;
  if (length < COMPOSER_MIN_LENGTH) {
    return "too_short";
  }
  return length > COMPOSER_MAX_LENGTH ? "too_long" : "ok";
}
