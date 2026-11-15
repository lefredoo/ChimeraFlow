"use client";

import { prettyRuleJson } from "../lib/rules/summary";
import { useI18n } from "./locale-provider";

/**
 * The rule JSON, pretty-printed in a scrollable block (focusable so the
 * keyboard can scroll it). React escapes the text: nothing here is HTML.
 */
export function RuleJson({ rule }: Readonly<{ rule: unknown }>) {
  const { t } = useI18n();
  return (
    <pre className="code-block font-mono" tabIndex={0} aria-label={t("rule.json.label")}>
      {prettyRuleJson(rule)}
    </pre>
  );
}
