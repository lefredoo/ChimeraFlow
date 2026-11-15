/**
 * Environment helpers (AGENTS.md section 7): no configuration fallback, fail fast.
 *
 * Next.js inlines `process.env.NEXT_PUBLIC_*` only for a literal property access,
 * so the caller reads the variable and passes the value; the name is used for the
 * error message only.
 */

/**
 * Return a required variable, or throw an error naming the variable and its use.
 *
 * @param name Variable name (for the error message).
 * @param description What the variable is for (for the error message).
 * @param value Value read by the caller (`process.env.NAME`).
 */
export function requireEnv(name: string, description: string, value: string | undefined): string {
  if (value === undefined || value.trim() === "") {
    throw new Error(`Required environment variable '${name}' is not set. Purpose: ${description}`);
  }
  return value;
}

/**
 * Return a required http(s) URL without trailing slash, or throw.
 *
 * @param name Variable name (for the error message).
 * @param description What the variable is for (for the error message).
 * @param value Value read by the caller (`process.env.NAME`).
 */
export function requireEnvUrl(name: string, description: string, value: string | undefined): string {
  const raw = requireEnv(name, description, value).trim();
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`Environment variable '${name}' must be a valid URL, got '${raw}'`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`Environment variable '${name}' must use http or https, got '${raw}'`);
  }
  return raw.replace(/\/+$/, "");
}

/**
 * Return an optional variable, or undefined when it is unset or empty.
 *
 * @param value Value read by the caller (`process.env.NAME`).
 */
export function optionalEnv(value: string | undefined): string | undefined {
  return value === undefined || value.trim() === "" ? undefined : value;
}
