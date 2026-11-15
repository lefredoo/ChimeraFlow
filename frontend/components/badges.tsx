"use client";

import type { RuleStatus, Severity, SourceName } from "../lib/api-types";
import type { MessageKey } from "../lib/i18n";
import { SeverityIcon, SourceIcon } from "./icons";
import { useI18n } from "./locale-provider";

const SOURCE_LABEL_KEYS: Record<SourceName, MessageKey> = {
  excel: "source.excel",
  access: "source.access",
  whatsapp: "source.whatsapp",
  momo: "source.momo",
};

const SEVERITY_LABEL_KEYS: Record<Severity, MessageKey> = {
  info: "severity.info",
  warning: "severity.warning",
  error: "severity.error",
};

const RULE_STATUS_LABEL_KEYS: Record<RuleStatus, MessageKey> = {
  active: "rule.status.active",
  inactive: "rule.status.inactive",
  draft: "rule.status.draft",
};

/** Source name with its icon and color: three cues, so color is never alone. */
export function SourceBadge({ source }: Readonly<{ source: SourceName }>) {
  const { t } = useI18n();
  return (
    <span className="source-badge" data-source={source}>
      <SourceIcon source={source} />
      {t(SOURCE_LABEL_KEYS[source])}
    </span>
  );
}

export function SeverityBadge({ severity }: Readonly<{ severity: Severity }>) {
  const { t } = useI18n();
  return (
    <span className="severity-badge" data-severity={severity}>
      <SeverityIcon severity={severity} />
      {t(SEVERITY_LABEL_KEYS[severity])}
    </span>
  );
}

export function RuleStatusBadge({ status }: Readonly<{ status: RuleStatus }>) {
  const { t } = useI18n();
  return (
    <span className="status-badge" data-rule-status={status}>
      {t(RULE_STATUS_LABEL_KEYS[status])}
    </span>
  );
}

export function useSourceLabel(): (source: SourceName) => string {
  const { t } = useI18n();
  return (source) => t(SOURCE_LABEL_KEYS[source]);
}
