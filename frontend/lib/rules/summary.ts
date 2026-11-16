import type { JsonValue, Operator, RuleCondition, RuleDraft, Severity, SourceName } from "../api-types";

export interface ConditionSummary {
  field: string;
  op: Operator;
  /** The literal value as display text (arrays joined, strings as is); empty when the condition uses `ref`. */
  value: string;
  /** "source.field" of a record already matched, when the condition compares with one. */
  ref: string | null;
  /** With `ref`: the tolerance in percent applied to the relative gap. */
  tolerancePct: number | null;
}

export interface JoinSummary {
  source: SourceName;
  /** Excel sheet or Access table the join reads, when the rule names one. */
  location: { kind: "sheet" | "table"; name: string } | null;
  /** Field of the joined source matched against the trigger entity. */
  field: string;
  conditions: ConditionSummary[];
}

export interface RuleSummary {
  trigger: { source: SourceName; entity: string; conditions: ConditionSummary[] };
  joins: JoinSummary[];
  windowSeconds: number;
  severity: Severity;
}

function formatValue(value: JsonValue): string {
  if (Array.isArray(value)) {
    return value.map(formatValue).join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

function summarizeConditions(conditions: readonly RuleCondition[] | undefined): ConditionSummary[] {
  return (conditions ?? []).map((condition) => ({
    field: condition.field,
    op: condition.op,
    value: condition.value === undefined ? "" : formatValue(condition.value),
    ref: condition.ref ?? null,
    tolerancePct: condition.tolerance_pct ?? null,
  }));
}

/**
 * Structure behind the human-readable description of a rule. The component
 * turns it into sentences with the i18n catalog, so no text is built here.
 */
export function summarizeRule(rule: RuleDraft): RuleSummary {
  return {
    trigger: {
      source: rule.trigger.source,
      entity: rule.trigger.entity,
      conditions: summarizeConditions(rule.trigger.where),
    },
    joins: rule.joins.map((join) => {
      let location: JoinSummary["location"] = null;
      if (join.sheet !== undefined) {
        location = { kind: "sheet", name: join.sheet };
      } else if (join.table !== undefined) {
        location = { kind: "table", name: join.table };
      }
      return {
        source: join.source,
        location,
        field: join.on.field,
        conditions: summarizeConditions(join.where),
      };
    }),
    windowSeconds: rule.window_seconds,
    severity: rule.emit.severity,
  };
}

/** The rule JSON as shown in the detail drawer and the composer preview. */
export function prettyRuleJson(rule: unknown): string {
  return JSON.stringify(rule, null, 2);
}
