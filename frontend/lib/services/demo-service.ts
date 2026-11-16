import { requestJson, type ApiResult } from "./http";

export interface DemoResetSummary {
  correlationsDeleted: number;
  executionsDeleted: number;
}

function parseResetSummary(data: unknown): DemoResetSummary | undefined {
  if (typeof data !== "object" || data === null) {
    return undefined;
  }
  const { correlations_deleted: correlations, executions_deleted: executions } = data as Record<string, unknown>;
  return typeof correlations === "number" && typeof executions === "number"
    ? { correlationsDeleted: correlations, executionsDeleted: executions }
    : undefined;
}

/** Put the shared demo back in its shipped state (`POST /api/v1/demo/reset`). */
export function resetDemo(): Promise<ApiResult<DemoResetSummary>> {
  return requestJson("/api/v1/demo/reset", { method: "POST" }, parseResetSummary);
}
