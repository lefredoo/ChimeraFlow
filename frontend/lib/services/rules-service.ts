import type { Language, Rule, RuleConversion, RuleDraft } from "../api-types";
import { isRule, parseRuleConversion, parseRules } from "../parsers";
import { jsonBody, requestJson, requestVoid, type ApiResult } from "./http";

export function fetchRules(): Promise<ApiResult<Rule[]>> {
  return requestJson("/api/v1/rules", {}, parseRules);
}

export function fetchPredefinedRules(): Promise<ApiResult<Rule[]>> {
  return requestJson("/api/v1/rules/predefined", {}, parseRules);
}

/** Convert a sentence into a draft rule. Nothing is stored. */
export function convertText(text: string, language: Language): Promise<ApiResult<RuleConversion>> {
  return requestJson("/api/v1/rules/from-text", jsonBody("POST", { text, language }), parseRuleConversion);
}

/** Store a reviewed draft. The draft is sent as received, extra fields included. */
export function createRule(draft: RuleDraft): Promise<ApiResult<Rule>> {
  return requestJson("/api/v1/rules", jsonBody("POST", draft), (data) => (isRule(data) ? data : undefined));
}

export function deleteRule(ruleId: string): Promise<ApiResult<null>> {
  return requestVoid(`/api/v1/rules/${encodeURIComponent(ruleId)}`, { method: "DELETE" });
}
