"use client";

import type { RuleDraft } from "../lib/api-types";
import type { MessageKey } from "../lib/i18n";
import { formatWindow } from "../lib/format";
import { OPERATOR_KEYS } from "../lib/operator-keys";
import { summarizeRule, type ConditionSummary, type JoinSummary } from "../lib/rules/summary";
import { SeverityBadge, useSourceLabel } from "./badges";
import { useI18n } from "./locale-provider";

function ConditionText({ condition }: Readonly<{ condition: ConditionSummary }>) {
  const { t } = useI18n();
  const op = t(OPERATOR_KEYS[condition.op]);
  if (condition.ref !== null && condition.tolerancePct !== null) {
    return <>{t("rule.summary.condition.gap", { field: condition.field, ref: condition.ref, op, tolerance: condition.tolerancePct })}</>;
  }
  if (condition.ref !== null) {
    return <>{t("rule.summary.condition.ref", { field: condition.field, op, ref: condition.ref })}</>;
  }
  return <>{t("rule.summary.condition", { field: condition.field, op, value: condition.value })}</>;
}

function Conditions({ conditions }: Readonly<{ conditions: readonly ConditionSummary[] }>) {
  if (conditions.length === 0) {
    return null;
  }
  return (
    <ul className="summary-conditions">
      {conditions.map((condition) => (
        <li key={`${condition.field}:${condition.op}:${condition.value}:${condition.ref ?? ""}`}>
          <ConditionText condition={condition} />
        </li>
      ))}
    </ul>
  );
}

function JoinLine({ join }: Readonly<{ join: JoinSummary }>) {
  const { t } = useI18n();
  const sourceLabel = useSourceLabel();
  const params = { source: sourceLabel(join.source), field: join.field, name: join.location?.name ?? "" };
  let key: MessageKey = "rule.summary.join";
  if (join.location?.kind === "sheet") {
    key = "rule.summary.join.sheet";
  } else if (join.location?.kind === "table") {
    key = "rule.summary.join.table";
  }
  return (
    <li>
      {t(key, params)}
      <Conditions conditions={join.conditions} />
    </li>
  );
}

/**
 * A rule in words: what triggers it, which sources it joins, the time window
 * and what it emits. The text values (entity, fields, template) come from the
 * rule JSON and are rendered as text only.
 */
export function RuleSummary({ rule }: Readonly<{ rule: RuleDraft }>) {
  const { t, locale } = useI18n();
  const sourceLabel = useSourceLabel();
  const summary = summarizeRule(rule);
  return (
    <div className="rule-summary">
      <ol className="summary-steps">
        <li>
          {t("rule.summary.trigger", { source: sourceLabel(summary.trigger.source), entity: summary.trigger.entity })}
          <Conditions conditions={summary.trigger.conditions} />
        </li>
        {summary.joins.map((join, index) => (
          // A rule may join the same source twice: the position is the identity
          <JoinLine key={index} join={join} />
        ))}
        <li>{t("rule.summary.window", { duration: formatWindow(summary.windowSeconds, locale) })}</li>
        <li>
          <span className="summary-emit">
            {t("rule.summary.emit")} <SeverityBadge severity={summary.severity} />
          </span>
          <code className="font-mono summary-template">{rule.emit.template}</code>
        </li>
      </ol>
    </div>
  );
}
