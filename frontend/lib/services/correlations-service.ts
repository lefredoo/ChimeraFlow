import type { Correlation, ExecutionSummary, Severity } from "../api-types";
import { parseCorrelations, parseExecutionSummary } from "../parsers";
import { requestJson, type ApiResult } from "./http";

export const CORRELATIONS_LIMIT = 200;

export interface CorrelationQuery {
  ruleId?: string;
  severity?: Severity;
  limit?: number;
}

/** Latest correlations first. */
export function fetchCorrelations(query: CorrelationQuery = {}): Promise<ApiResult<Correlation[]>> {
  const params = new URLSearchParams();
  if (query.ruleId !== undefined) {
    params.set("rule_id", query.ruleId);
  }
  if (query.severity !== undefined) {
    params.set("severity", query.severity);
  }
  params.set("limit", String(query.limit ?? CORRELATIONS_LIMIT));
  return requestJson(`/api/v1/correlations?${params.toString()}`, {}, parseCorrelations);
}

/** Run every active rule on the current data. */
export function executeRules(): Promise<ApiResult<ExecutionSummary>> {
  return requestJson("/api/v1/correlations/execute", { method: "POST" }, parseExecutionSummary);
}
