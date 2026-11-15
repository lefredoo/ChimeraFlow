"use client";

import { useId } from "react";

import type { JsonValue } from "../lib/api-types";
import {
  displayValue,
  parseExplanation,
  type ConditionOutcome,
  type JoinExplanation,
  type StructuredExplanation,
} from "../lib/explanation";
import type { MessageKey } from "../lib/i18n";
import { OPERATOR_KEYS } from "../lib/operator-keys";
import { formatScore } from "../lib/sandbox";
import { SourceBadge } from "./badges";
import { StatusIcon } from "./icons";
import { useI18n } from "./locale-provider";

const MAX_DEPTH = 4;

const METHOD_KEYS: Record<string, MessageKey> = {
  exact: "explanation.match.exact",
  synonym: "explanation.match.synonym",
  fuzzy: "explanation.match.fuzzy",
  token: "explanation.match.token",
};

/** A JSON value as nested lists. Every string is rendered as React text, never as HTML. */
function GenericValue({ value, depth }: Readonly<{ value: JsonValue; depth: number }>) {
  const { t } = useI18n();
  if (value === null) {
    return <span className="text-muted">{t("common.none")}</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? t("common.yes") : t("common.no")}</span>;
  }
  if (typeof value !== "object") {
    return <span className="explanation-text">{String(value)}</span>;
  }
  if (depth >= MAX_DEPTH) {
    return <code className="font-mono explanation-text">{JSON.stringify(value)}</code>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="explanation-list">
        {value.map((item, index) => (
          // Positions are the only identity of unnamed list items
          <li key={index}>
            <GenericValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <dl className="explanation-fields">
      {Object.entries(value).map(([name, item]) => (
        <div key={name} className="explanation-field">
          <dt className="font-mono">{name}</dt>
          <dd>
            <GenericValue value={item} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Outcome({ outcome }: Readonly<{ outcome: ConditionOutcome }>) {
  const { t, locale } = useI18n();
  const op = t(OPERATOR_KEYS[outcome.op]);
  const expected = displayValue(outcome.expected);
  const actual = outcome.actual === null ? t("common.none") : displayValue(outcome.actual);
  let text: string;
  if (outcome.ref !== null && outcome.tolerancePct !== null) {
    const gap = outcome.gapPct === null ? t("common.unknown") : new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(outcome.gapPct);
    text = t("explanation.outcome.gap", {
      field: outcome.field,
      actual,
      ref: outcome.ref,
      expected,
      gap,
      op,
      tolerance: outcome.tolerancePct,
    });
  } else if (outcome.ref !== null) {
    text = t("explanation.outcome.ref", { field: outcome.field, op, ref: outcome.ref, expected, actual });
  } else {
    text = t("explanation.outcome", { field: outcome.field, op, expected, actual });
  }
  return (
    <li className="outcome" data-passed={outcome.passed}>
      <StatusIcon status={outcome.passed ? "ok" : "error"} />
      <span>
        {text} <span className="outcome-state">{outcome.passed ? t("explanation.passed") : t("explanation.failed")}</span>
      </span>
    </li>
  );
}

function Outcomes({ outcomes }: Readonly<{ outcomes: readonly ConditionOutcome[] }>) {
  if (outcomes.length === 0) {
    return null;
  }
  return (
    <ul className="outcome-list">
      {outcomes.map((outcome, index) => (
        // The same field can be tested twice: the position is the identity
        <Outcome key={index} outcome={outcome} />
      ))}
    </ul>
  );
}

function JoinStep({ join }: Readonly<{ join: JoinExplanation }>) {
  const { t, locale } = useI18n();
  const methodKey = join.method === null ? undefined : METHOD_KEYS[join.method];
  const score = join.score === null ? t("common.unknown") : formatScore(join.score, locale);
  return (
    <li className="why-step">
      <SourceBadge source={join.source} />
      <p className="why-text">{t("explanation.join", { raw: join.candidate.raw, norm: join.candidate.norm })}</p>
      {join.method !== null && (
        <p className="why-text text-secondary">
          {methodKey === undefined
            ? t("explanation.match.unknown", { method: join.method, score })
            : t(methodKey, { score })}
        </p>
      )}
      <Outcomes outcomes={join.where} />
    </li>
  );
}

function StructuredView({ explanation }: Readonly<{ explanation: StructuredExplanation }>) {
  const { t } = useI18n();
  const { trigger, joins } = explanation;
  return (
    <ol className="why-steps">
      <li className="why-step">
        <SourceBadge source={trigger.source} />
        <p className="why-text">{t("explanation.trigger", { raw: trigger.entity.raw, norm: trigger.entity.norm })}</p>
        <Outcomes outcomes={trigger.where} />
      </li>
      {joins.map((join, index) => (
        // A rule may join the same source twice: the position is the identity
        <JoinStep key={index} join={join} />
      ))}
    </ol>
  );
}

/**
 * "Why this matches" panel. It reads the engine's explanation (trigger entity,
 * candidate and score of each join, outcome of each condition) and falls back
 * to a generic display for any other shape. The card shows this panel only
 * when the correlation has an explanation.
 */
export function ExplanationPanel({ explanation }: Readonly<{ explanation: JsonValue }>) {
  const { t } = useI18n();
  const headingId = useId();
  const structured = parseExplanation(explanation);
  return (
    <section className="explanation" aria-labelledby={headingId}>
      <h3 id={headingId} className="explanation-title">
        {t("explanation.title")}
      </h3>
      {structured === null ? <GenericValue value={explanation} depth={0} /> : <StructuredView explanation={structured} />}
    </section>
  );
}
