"use client";

import type { SourceInfo, SourceName } from "../lib/api-types";
import type { MessageKey } from "../lib/i18n";
import { formatRelativeTime } from "../lib/format";
import { RECORD_COUNT_CAP } from "../lib/services/sources-service";
import { SourceBadge } from "./badges";
import { StatusIcon } from "./icons";
import { useI18n } from "./locale-provider";

const DESCRIPTION_KEYS: Record<SourceName, MessageKey> = {
  excel: "sources.excel.description",
  access: "sources.access.description",
  whatsapp: "sources.whatsapp.description",
  momo: "sources.momo.description",
};

const STATUS_KEYS: Record<SourceInfo["status"], MessageKey> = {
  ok: "sourceStatus.ok",
  degraded: "sourceStatus.degraded",
  error: "sourceStatus.error",
};

interface SourceHealthCardProps {
  source: SourceInfo;
  /** Records read from this source, or undefined when the count is not known. */
  recordCount: number | undefined;
  now: number;
}

/** Health of one source: status (icon and text), record count and last read. */
export function SourceHealthCard({ source, recordCount, now }: Readonly<SourceHealthCardProps>) {
  const { t, tp, locale } = useI18n();
  const lastFetch = source.lastFetch === null ? null : formatRelativeTime(source.lastFetch, now, locale);
  let countText = t("common.unknown");
  if (recordCount !== undefined) {
    countText =
      recordCount >= RECORD_COUNT_CAP
        ? t("sources.records.atLeast", { count: new Intl.NumberFormat(locale).format(RECORD_COUNT_CAP) })
        : tp("sources.records", recordCount);
  }
  return (
    <article className="source-card glass-panel" data-source={source.name} data-status={source.status}>
      <SourceBadge source={source.name} />
      <p className="text-secondary source-card-description">{t(DESCRIPTION_KEYS[source.name])}</p>
      <p className="source-status" data-status={source.status}>
        <StatusIcon status={source.status} />
        {t(STATUS_KEYS[source.status])}
      </p>
      <dl className="meta-list">
        <div>
          <dt>{t("sources.recordsLabel")}</dt>
          <dd className="font-mono">{countText}</dd>
        </div>
        <div>
          <dt>{t("sources.lastFetch")}</dt>
          <dd>{lastFetch ?? t("sources.neverFetched")}</dd>
        </div>
      </dl>
    </article>
  );
}
