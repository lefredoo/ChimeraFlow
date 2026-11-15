import { requireEnv } from "./env";

/**
 * Demo account shown on the login page. These values are public by design
 * (they ship in the client bundle): the account only reads synthetic data.
 * Evaluated when the module is first imported, so a missing variable stops
 * `next build`.
 */
export const DEMO_LOGIN_EMAIL = requireEnv(
  "NEXT_PUBLIC_DEMO_LOGIN_EMAIL",
  "Email of the public demo account displayed on the login page",
  process.env.NEXT_PUBLIC_DEMO_LOGIN_EMAIL,
);

export const DEMO_LOGIN_PASSWORD = requireEnv(
  "NEXT_PUBLIC_DEMO_LOGIN_PASSWORD",
  "Password of the public demo account displayed on the login page",
  process.env.NEXT_PUBLIC_DEMO_LOGIN_PASSWORD,
);
