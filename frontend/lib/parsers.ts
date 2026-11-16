import {
  OPERATORS,
  SEVERITIES,
  SOURCE_NAMES,
  type Correlation,
  type ExecutionSummary,
  type JsonValue,
  type NormalizeComparison,
  type NormalizedForms,
  type NormalizeResult,
  type Operator,
  type Provenance,
  type Rule,
  type RuleConversion,
  type RuleDraft,
  type RuleStatus,
  type Severity,
  type SourceInfo,
  type SourceName,
  type SourceStatus,
} from "./api-types";

/**
 * Runtime checks of API payloads. Fetch gives `unknown`: a guard narrows it
 * without copying, so fields this client does not know are kept (they are
 * shown in the rule JSON and sent back when a draft is saved).
 */

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isSourceName(value: unknown): value is SourceName {
  return typeof value === "string" && (SOURCE_NAMES as readonly string[]).includes(value);
}

export function isSeverity(value: unknown): value is Severity {
  return typeof value === "string" && (SEVERITIES as readonly string[]).includes(value);
}

function isOperator(value: unknown): value is Operator {
  return typeof value === "string" && (OPERATORS as readonly string[]).includes(value);
}

function isRuleStatus(value: unknown): value is RuleStatus {
  return value === "active" || value === "inactive" || value === "draft";
}

function isSourceStatus(value: unknown): value is SourceStatus {
  return value === "ok" || value === "degraded" || value === "error";
}

export function isJsonValue(value: unknown, depth = 0): value is JsonValue {
  if (depth > 8) {
    return false;
  }
  if (value === null || ["string", "number", "boolean"].includes(typeof value)) {
    return true;
  }
  if (Array.isArray(value)) {
    return value.every((item) => isJsonValue(item, depth + 1));
  }
  return isRecord(value) && Object.values(value).every((item) => isJsonValue(item, depth + 1));
}

function isCondition(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.field === "string" &&
    isOperator(value.op) &&
    (value.value === undefined || isJsonValue(value.value)) &&
    (value.ref === undefined || typeof value.ref === "string") &&
    (value.tolerance_pct === undefined || typeof value.tolerance_pct === "number")
  );
}

function isJoin(value: unknown): boolean {
  if (!isRecord(value) || !isSourceName(value.source) || !isRecord(value.on)) {
    return false;
  }
  const where = value.where;
  return (
    typeof value.on.entity === "string" &&
    typeof value.on.field === "string" &&
    (where === undefined || (Array.isArray(where) && where.every(isCondition)))
  );
}

export function isRuleDraft(value: unknown): value is RuleDraft {
  if (!isRecord(value) || !isRecord(value.trigger) || !isRecord(value.emit)) {
    return false;
  }
  const triggerWhere = value.trigger.where;
  return (
    typeof value.id === "string" &&
    typeof value.natural_language === "string" &&
    isSourceName(value.trigger.source) &&
    typeof value.trigger.entity === "string" &&
    (triggerWhere === undefined || (Array.isArray(triggerWhere) && triggerWhere.every(isCondition))) &&
    Array.isArray(value.joins) &&
    value.joins.every(isJoin) &&
    typeof value.window_seconds === "number" &&
    isSeverity(value.emit.severity) &&
    typeof value.emit.template === "string"
  );
}

export function isRule(value: unknown): value is Rule {
  return (
    isRuleDraft(value) &&
    isRecord(value) &&
    typeof value.version === "number" &&
    isRuleStatus(value.status) &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

function isProvenance(value: unknown): value is Provenance {
  return (
    isRecord(value) &&
    isSourceName(value.source) &&
    typeof value.source_ref === "string" &&
    typeof value.record_id === "string"
  );
}

export function isCorrelation(value: unknown): value is Correlation {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    typeof value.rule_id === "string" &&
    typeof value.detected_at === "string" &&
    isSeverity(value.severity) &&
    typeof value.message === "string" &&
    Array.isArray(value.provenance) &&
    value.provenance.every(isProvenance) &&
    (value.explanation === undefined || value.explanation === null || isJsonValue(value.explanation))
  );
}

export function parseRules(data: unknown): Rule[] | undefined {
  return Array.isArray(data) && data.every(isRule) ? data : undefined;
}

export function parseCorrelations(data: unknown): Correlation[] | undefined {
  return Array.isArray(data) && data.every(isCorrelation) ? data : undefined;
}

export function parseRuleConversion(data: unknown): RuleConversion | undefined {
  if (!isRecord(data) || !isRuleDraft(data.rule) || typeof data.retries !== "number") {
    return undefined;
  }
  return { rule: data.rule, retries: data.retries };
}

export function parseSources(data: unknown): SourceInfo[] | undefined {
  if (!isRecord(data) || !Array.isArray(data.sources)) {
    return undefined;
  }
  const sources: SourceInfo[] = [];
  for (const entry of data.sources) {
    if (!isRecord(entry) || !isSourceName(entry.name)) {
      return undefined;
    }
    sources.push({
      name: entry.name,
      // An unknown status is shown as an error: never as healthy by default
      status: isSourceStatus(entry.status) ? entry.status : "error",
      message: typeof entry.message === "string" ? entry.message : "",
      lastFetch: typeof entry.last_fetch === "string" ? entry.last_fetch : null,
    });
  }
  return sources;
}

/** Count of records per source from `GET /sources/all/records`. */
export function parseRecordCounts(data: unknown): Partial<Record<SourceName, number>> | undefined {
  if (!isRecord(data) || !Array.isArray(data.records)) {
    return undefined;
  }
  const counts: Partial<Record<SourceName, number>> = {};
  for (const record of data.records) {
    if (isRecord(record) && isSourceName(record.source)) {
      counts[record.source] = (counts[record.source] ?? 0) + 1;
    }
  }
  return counts;
}

export function parseExecutionSummary(data: unknown): ExecutionSummary | undefined {
  if (!isRecord(data)) {
    return undefined;
  }
  const { rules_executed: executed, rules_failed: failed, correlations_found: found } = data;
  if (typeof executed !== "number" || typeof failed !== "number" || typeof found !== "number") {
    return undefined;
  }
  if (data.status === "no_rules") {
    return { status: "no_rules", rules_executed: 0, rules_failed: 0, correlations_found: 0 };
  }
  if (data.status === "success" && typeof data.records_scanned === "number" && typeof data.duration_ms === "number") {
    return {
      status: "success",
      rules_executed: executed,
      rules_failed: failed,
      correlations_found: found,
      records_scanned: data.records_scanned,
      duration_ms: data.duration_ms,
    };
  }
  return undefined;
}

function toStringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  // The API may send numbers as numbers or strings: both are displayed as text
  return value.every((item) => typeof item === "string" || typeof item === "number") ? value.map(String) : undefined;
}

function parseForms(entry: unknown): NormalizedForms | undefined {
  if (!isRecord(entry)) {
    return undefined;
  }
  const tokens = toStringList(entry.tokens);
  const numbers = toStringList(entry.numbers);
  if (
    typeof entry.text !== "string" ||
    typeof entry.norm !== "string" ||
    typeof entry.canonical !== "string" ||
    tokens === undefined ||
    numbers === undefined
  ) {
    return undefined;
  }
  return { text: entry.text, norm: entry.norm, canonical: entry.canonical, tokens, numbers };
}

function parseComparison(entry: unknown): NormalizeComparison | undefined {
  const forms = parseForms(entry);
  if (forms === undefined || !isRecord(entry) || typeof entry.score !== "number" || typeof entry.matched !== "boolean") {
    return undefined;
  }
  return { ...forms, score: entry.score, matched: entry.matched, method: typeof entry.method === "string" ? entry.method : null };
}

/** Answer of `POST /api/v1/normalize`: the reference text and its comparisons. */
export function parseNormalizeResult(data: unknown): NormalizeResult | undefined {
  const forms = parseForms(data);
  if (forms === undefined || !isRecord(data) || !Array.isArray(data.comparisons)) {
    return undefined;
  }
  const comparisons: NormalizeComparison[] = [];
  for (const entry of data.comparisons) {
    const comparison = parseComparison(entry);
    if (comparison === undefined) {
      return undefined;
    }
    comparisons.push(comparison);
  }
  return { ...forms, comparisons };
}
