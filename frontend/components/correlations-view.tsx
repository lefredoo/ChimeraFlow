"use client";

import { useId, useMemo, useState } from "react";

import { useLiveCorrelations, type LiveMode } from "../hooks/use-live-correlations";
import { useNow } from "../hooks/use-now";
import { SEVERITIES, type Severity } from "../lib/api-types";
import { filterCorrelations, NO_FILTERS, ruleIdsOf, type CorrelationFilters } from "../lib/correlations/filter";
import { formatRelativeTime } from "../lib/format";
import type { MessageKey } from "../lib/i18n";
import { CorrelationCard } from "./correlation-card";
import { ErrorNotice, LoadingNote, PageHeading } from "./feedback";
import { useI18n } from "./locale-provider";

const MODE_KEYS: Record<LiveMode, MessageKey> = {
  connecting: "correlations.live.connecting",
  stream: "correlations.live.stream",
  polling: "correlations.live.polling",
};

const SEVERITY_KEYS: Record<Severity, MessageKey> = {
  info: "severity.info",
  warning: "severity.warning",
  error: "severity.error",
};

export function CorrelationsView() {
  const { t, tp, locale } = useI18n();
  const ids = useId();
  const now = useNow(15_000);
  const live = useLiveCorrelations();
  const [filters, setFilters] = useState<CorrelationFilters>(NO_FILTERS);

  const all = useMemo(() => (live.state.status === "ready" ? live.state.correlations : []), [live.state]);
  const ruleIds = useMemo(() => ruleIdsOf(all), [all]);
  const visible = useMemo(() => filterCorrelations(all, filters), [all, filters]);
  const refreshed = live.refreshedAt === null ? null : formatRelativeTime(new Date(live.refreshedAt).toISOString(), now, locale);
  const filtering = filters.severity !== "" || filters.ruleId !== "";

  return (
    <>
      <PageHeading title={t("correlations.title")} lead={t("correlations.lead")} />

      <div className="toolbar-row">
        <p className="live-indicator" data-mode={live.mode}>
          <span className="live-dot" aria-hidden="true" />
          {t(MODE_KEYS[live.mode])}
          {refreshed !== null && <span className="text-muted">{t("correlations.live.updated", { time: refreshed })}</span>}
        </p>
        <button type="button" className="button button-secondary" onClick={live.refresh}>
          {t("correlations.refresh")}
        </button>
      </div>

      <form className="filters" role="search" aria-label={t("correlations.filters")} onSubmit={(event) => event.preventDefault()}>
        <div className="form-field">
          <label htmlFor={`${ids}-severity`} className="form-label">
            {t("correlations.filter.severity")}
          </label>
          <select
            id={`${ids}-severity`}
            className="form-input form-select"
            value={filters.severity}
            onChange={(event) => {
              const value = event.target.value;
              setFilters({ ...filters, severity: SEVERITIES.find((severity) => severity === value) ?? "" });
            }}
          >
            <option value="">{t("correlations.filter.all")}</option>
            {SEVERITIES.map((severity) => (
              <option key={severity} value={severity}>
                {t(SEVERITY_KEYS[severity])}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor={`${ids}-rule`} className="form-label">
            {t("correlations.filter.rule")}
          </label>
          <select
            id={`${ids}-rule`}
            className="form-input form-select"
            value={filters.ruleId}
            onChange={(event) => setFilters({ ...filters, ruleId: event.target.value })}
          >
            <option value="">{t("correlations.filter.all")}</option>
            {ruleIds.map((ruleId) => (
              <option key={ruleId} value={ruleId}>
                {ruleId}
              </option>
            ))}
          </select>
        </div>
        {filtering && (
          <button type="button" className="button button-secondary" onClick={() => setFilters(NO_FILTERS)}>
            {t("correlations.filter.reset")}
          </button>
        )}
      </form>

      {live.state.status === "loading" && <LoadingNote />}
      {live.state.status === "failed" && <ErrorNotice error={live.state.error} onRetry={live.refresh} />}
      {live.state.status === "ready" && (
        <section aria-label={t("correlations.title")}>
          <p className="text-muted" aria-live="polite">
            {tp("correlations.shown", visible.length)}
          </p>
          {all.length === 0 && <p className="text-secondary">{t("correlations.empty")}</p>}
          {all.length > 0 && visible.length === 0 && <p className="text-secondary">{t("correlations.emptyFiltered")}</p>}
          <div className="card-stack">
            {visible.map((correlation) => (
              <CorrelationCard key={correlation.id} correlation={correlation} now={now} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
