import type { SourceInfo, SourceName } from "../api-types";
import { parseRecordCounts, parseSources } from "../parsers";
import { requestJson, type ApiResult } from "./http";

/** Records read per source to count them. Counts at this value mean "at least". */
export const RECORD_COUNT_CAP = 500;

export type RecordCounts = Partial<Record<SourceName, number>>;

/** Sources with their health (`GET /api/v1/sources`). */
export function fetchSources(): Promise<ApiResult<SourceInfo[]>> {
  return requestJson("/api/v1/sources", {}, parseSources);
}

/** Record count per source, from one `all/records` read capped at `RECORD_COUNT_CAP`. */
export function fetchRecordCounts(): Promise<ApiResult<RecordCounts>> {
  return requestJson(`/api/v1/sources/all/records?limit_per_source=${RECORD_COUNT_CAP}`, {}, parseRecordCounts);
}
