import type { MessageKey, MessageParams } from "./i18n";
import type { ApiError } from "./services/http";

export interface ErrorMessage {
  key: MessageKey;
  params?: MessageParams;
}

const CODE_KEYS: Readonly<Record<string, MessageKey>> = {
  auth_required: "error.session",
  auth_token_invalid: "error.session",
  auth_token_expired: "error.session",
  rule_not_found: "error.rule_not_found",
  rule_already_exists: "error.rule_already_exists",
  rate_limit_unavailable: "error.rate_limit_unavailable",
  nl_feature_disabled: "error.nl_feature_disabled",
  nl_budget_exceeded: "error.nl_budget_exceeded",
  nl_budget_unavailable: "error.nl_budget_exceeded",
  nl_provider_error: "error.nl_provider_error",
  nl_conversion_failed: "error.nl_conversion_failed",
  source_not_found: "error.source_not_found",
  source_fetch_failed: "error.source_fetch_failed",
};

/**
 * Map an API failure to the message shown to the user.
 *
 * The API's own `message` is a developer hint in English and is never shown:
 * the stable `code` selects a translated message instead.
 */
export function describeApiError(error: ApiError): ErrorMessage {
  if (error.kind === "network") {
    return { key: "error.network" };
  }
  if (error.kind === "invalid_response") {
    return { key: "error.invalid_response" };
  }
  if (error.code === "rate_limit_exceeded" || error.status === 429) {
    return error.retryAfterSeconds === undefined
      ? { key: "error.rate_limit_exceeded_no_delay" }
      : { key: "error.rate_limit_exceeded", params: { seconds: error.retryAfterSeconds } };
  }
  if (error.code !== undefined && Object.prototype.hasOwnProperty.call(CODE_KEYS, error.code)) {
    return { key: CODE_KEYS[error.code] };
  }
  if (error.status === 404) {
    return { key: "error.not_found" };
  }
  if (error.status === 422) {
    return { key: "error.validation" };
  }
  return { key: "error.generic" };
}
