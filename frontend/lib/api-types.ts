/**
 * Types of the backend API payloads (see .kiro/specs/api-spec.md).
 *
 * Rule and correlation fields keep the API's snake_case names: the rule JSON is
 * shown and sent back to the API as is, and extra fields added by newer backend
 * versions (trigger-side `where`, `explanation`) must survive a round trip.
 */

export const SOURCE_NAMES = ["excel", "access", "whatsapp", "momo"] as const;
export type SourceName = (typeof SOURCE_NAMES)[number];

export type SourceStatus = "ok" | "degraded" | "error";

export interface SourceInfo {
  name: SourceName;
  status: SourceStatus;
  message: string;
  lastFetch: string | null;
}

export type Severity = "info" | "warning" | "error";
export const SEVERITIES: readonly Severity[] = ["info", "warning", "error"];

export type RuleStatus = "active" | "inactive" | "draft";

export const OPERATORS = ["eq", "ne", "lt", "lte", "gt", "gte", "contains", "in"] as const;
export type Operator = (typeof OPERATORS)[number];

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

/** `field <op> value`, or `field <op> ref` ("source.field" of a record already matched). */
export interface RuleCondition {
  field: string;
  op: Operator;
  value?: JsonValue;
  ref?: string;
  /** With `ref`: compare the relative gap in percent with this tolerance. */
  tolerance_pct?: number;
}

export interface RuleTrigger {
  source: SourceName;
  entity: string;
  /** Trigger-side conditions (newer backend versions). */
  where?: RuleCondition[];
}

export interface RuleJoin {
  source: SourceName;
  table?: string;
  sheet?: string;
  on: { entity: string; field: string };
  where?: RuleCondition[];
}

export interface RuleEmit {
  severity: Severity;
  template: string;
}

/** A rule definition as sent to `POST /rules` (also the `rule` of a `from-text` answer). */
export interface RuleDraft {
  id: string;
  natural_language: string;
  trigger: RuleTrigger;
  joins: RuleJoin[];
  window_seconds: number;
  emit: RuleEmit;
}

/** A stored rule. */
export interface Rule extends RuleDraft {
  version: number;
  status: RuleStatus;
  created_at: string;
  updated_at: string;
}

export interface Provenance {
  source: SourceName;
  source_ref: string;
  record_id: string;
}

export interface Correlation {
  id: number;
  rule_id: string;
  detected_at: string;
  severity: Severity;
  message: string;
  provenance: Provenance[];
  /** Why the records match. Present only when the backend sends it; shape not fixed. */
  explanation?: JsonValue;
}

export type ExecutionSummary =
  | { status: "no_rules"; rules_executed: 0; rules_failed: 0; correlations_found: 0 }
  | {
      status: "success";
      rules_executed: number;
      rules_failed: number;
      correlations_found: number;
      records_scanned: number;
      duration_ms: number;
    };

export interface RuleConversion {
  rule: RuleDraft;
  retries: number;
}

export type Language = "fr" | "en";

/** How a name is reduced before matching (`POST /api/v1/normalize`). */
export interface NormalizedForms {
  text: string;
  /** Lowercase, no accents, no punctuation: the key. */
  norm: string;
  /** `norm` with FR/EN synonyms replaced: what is compared. */
  canonical: string;
  tokens: string[];
  numbers: string[];
}

/** A compared name and its score against the reference text. */
export interface NormalizeComparison extends NormalizedForms {
  score: number;
  matched: boolean;
  /** exact, synonym, fuzzy or token; null when not matched. */
  method: string | null;
}

export interface NormalizeResult extends NormalizedForms {
  comparisons: NormalizeComparison[];
}
