import { describe, expect, it } from "vitest";

import { describeApiError } from "./error-messages";
import type { ApiError } from "./services/http";

function http(status: number, code?: string, retryAfterSeconds?: number): ApiError {
  return { kind: "http", status, code, retryAfterSeconds, fallbackRules: [] };
}

describe("describeApiError", () => {
  it.each([
    ["nl_feature_disabled", 503, "error.nl_feature_disabled"],
    ["nl_budget_exceeded", 503, "error.nl_budget_exceeded"],
    ["nl_budget_unavailable", 503, "error.nl_budget_exceeded"],
    ["nl_conversion_failed", 422, "error.nl_conversion_failed"],
    ["nl_provider_error", 502, "error.nl_provider_error"],
    ["rule_already_exists", 409, "error.rule_already_exists"],
    ["rule_not_found", 404, "error.rule_not_found"],
    ["auth_token_expired", 401, "error.session"],
    ["rate_limit_unavailable", 503, "error.rate_limit_unavailable"],
  ])("should map the code %s to its message", (code, status, key) => {
    expect(describeApiError(http(status, code)).key).toBe(key);
  });

  it("should give the delay when the rate limit answer has Retry-After", () => {
    expect(describeApiError(http(429, "rate_limit_exceeded", 42))).toEqual({
      key: "error.rate_limit_exceeded",
      params: { seconds: 42 },
    });
  });

  it("should omit the delay when the rate limit answer has no Retry-After", () => {
    expect(describeApiError(http(429, "rate_limit_exceeded")).key).toBe("error.rate_limit_exceeded_no_delay");
  });

  it("should treat a bare 429 as a rate limit", () => {
    expect(describeApiError(http(429)).key).toBe("error.rate_limit_exceeded_no_delay");
  });

  it("should map a network failure to the network message", () => {
    expect(describeApiError({ kind: "network" }).key).toBe("error.network");
  });

  it("should map an unexpected body to the invalid response message", () => {
    expect(describeApiError({ kind: "invalid_response" }).key).toBe("error.invalid_response");
  });

  it("should map a validation error without code to the validation message", () => {
    expect(describeApiError(http(422)).key).toBe("error.validation");
  });

  it("should fall back to the generic message for an unknown code", () => {
    expect(describeApiError(http(500, "something_new")).key).toBe("error.generic");
  });

  it("should not read an inherited property as a code", () => {
    expect(describeApiError(http(500, "constructor")).key).toBe("error.generic");
  });
});
