import { requireEnvUrl } from "./env";

/**
 * Backend API base URL. Evaluated when the module is first imported, so a
 * missing NEXT_PUBLIC_API_URL stops `next build` instead of shipping a bundle
 * that talks to the wrong host.
 */
export const API_URL = requireEnvUrl(
  "NEXT_PUBLIC_API_URL",
  "Base URL of the ChimeraFlow backend API",
  process.env.NEXT_PUBLIC_API_URL,
);
