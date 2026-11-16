import type { NormalizeResult } from "../api-types";
import { parseNormalizeResult } from "../parsers";
import { jsonBody, requestJson, type ApiResult } from "./http";

/**
 * Normalize `text` and score it against `compareWith` with the matcher of the
 * rule engine (`POST /api/v1/normalize`). A 404 means the backend does not
 * have the endpoint (older version).
 */
export function normalizeText(text: string, compareWith: readonly string[]): Promise<ApiResult<NormalizeResult>> {
  return requestJson("/api/v1/normalize", jsonBody("POST", { text, compare_with: compareWith }), parseNormalizeResult);
}
