import { OPERATORS, SOURCE_NAMES, type JsonValue, type Operator, type SourceName } from "./api-types";

/**
 * Structured reading of a correlation's `explanation` (engine/interpreter.py:
 * the trigger entity, then for each join the candidate chosen, its score and
 * method, and the outcome of every condition). Any other shape yields null and
 * the UI falls back to a generic display.
 */

export interface ConditionOutcome {
  field: string;
  op: Operator;
  expected: JsonValue;
  actual: JsonValue;
  passed: boolean;
  /** "source.field" when the condition compared with another matched record. */
  ref: string | null;
  tolerancePct: number | null;
  gapPct: number | null;
}

export interface EntityForms {
  raw: string;
  norm: string;
}

export interface TriggerExplanation {
  source: SourceName;
  recordId: string;
  entity: EntityForms;
  where: ConditionOutcome[];
}

export interface JoinExplanation {
  source: SourceName;
  recordId: string;
  candidate: EntityForms;
  /** Similarity in [0, 1] between the trigger entity and the candidate. */
  score: number | null;
  /** exact, synonym, fuzzy or token. */
  method: string | null;
  where: ConditionOutcome[];
}

export interface StructuredExplanation {
  trigger: TriggerExplanation;
  joins: JoinExplanation[];
}

type JsonObject = { [key: string]: JsonValue };

function asObject(value: JsonValue | undefined): JsonObject | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value : null;
}

function asSource(value: JsonValue | undefined): SourceName | null {
  return typeof value === "string" ? (SOURCE_NAMES.find((name) => name === value) ?? null) : null;
}

function asOperator(value: JsonValue | undefined): Operator | null {
  return typeof value === "string" ? (OPERATORS.find((op) => op === value) ?? null) : null;
}

function parseForms(value: JsonValue | undefined): EntityForms | null {
  const object = asObject(value);
  return object !== null && typeof object.raw === "string" && typeof object.norm === "string"
    ? { raw: object.raw, norm: object.norm }
    : null;
}

function parseOutcomes(value: JsonValue | undefined): ConditionOutcome[] | null {
  if (value === undefined) {
    return [];
  }
  if (!Array.isArray(value)) {
    return null;
  }
  const outcomes: ConditionOutcome[] = [];
  for (const entry of value) {
    const object = asObject(entry);
    const op = object === null ? null : asOperator(object.op);
    if (object === null || op === null || typeof object.field !== "string" || typeof object.passed !== "boolean") {
      return null;
    }
    outcomes.push({
      field: object.field,
      op,
      expected: object.expected ?? null,
      actual: object.actual ?? null,
      passed: object.passed,
      ref: typeof object.ref === "string" ? object.ref : null,
      tolerancePct: typeof object.tolerance_pct === "number" ? object.tolerance_pct : null,
      gapPct: typeof object.gap_pct === "number" ? object.gap_pct : null,
    });
  }
  return outcomes;
}

function parseTrigger(value: JsonValue | undefined): TriggerExplanation | null {
  const object = asObject(value);
  if (object === null) {
    return null;
  }
  const source = asSource(object.source);
  const entity = parseForms(object.entity);
  const where = parseOutcomes(object.where);
  if (source === null || entity === null || where === null || typeof object.record_id !== "string") {
    return null;
  }
  return { source, recordId: object.record_id, entity, where };
}

function parseJoin(value: JsonValue): JoinExplanation | null {
  const object = asObject(value);
  if (object === null) {
    return null;
  }
  const source = asSource(object.source);
  const candidate = parseForms(object.candidate);
  const where = parseOutcomes(object.where);
  if (source === null || candidate === null || where === null || typeof object.record_id !== "string") {
    return null;
  }
  return {
    source,
    recordId: object.record_id,
    candidate,
    score: typeof object.score === "number" ? object.score : null,
    method: typeof object.method === "string" ? object.method : null,
    where,
  };
}

/** The structured explanation, or null when `value` does not have the engine's shape. */
export function parseExplanation(value: JsonValue): StructuredExplanation | null {
  const object = asObject(value);
  if (object === null || !Array.isArray(object.joins)) {
    return null;
  }
  const trigger = parseTrigger(object.trigger);
  if (trigger === null) {
    return null;
  }
  const joins: JoinExplanation[] = [];
  for (const entry of object.joins) {
    const join = parseJoin(entry);
    if (join === null) {
      return null;
    }
    joins.push(join);
  }
  return { trigger, joins };
}

/** A JSON value as display text. */
export function displayValue(value: JsonValue): string {
  if (value === null) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(displayValue).join(", ");
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
