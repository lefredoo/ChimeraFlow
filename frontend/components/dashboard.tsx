"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { useLiveCorrelations } from "../hooks/use-live-correlations";
import { useNow } from "../hooks/use-now";
import { useResource } from "../hooks/use-resource";
import { SOURCE_NAMES, type ExecutionSummary } from "../lib/api-types";
import { countBySeverity } from "../lib/correlations/filter";
import { formatDuration, formatList, formatNumber } from "../lib/format";
import { unhealthySources } from "../lib/sources-health";
import { executeRules } from "../lib/services/correlations-service";
import type { ApiError } from "../lib/services/http";
import { fetchRules } from "../lib/services/rules-service";
import { fetchRecordCounts, fetchSources } from "../lib/services/sources-service";
import { ApiStatus } from "./api-status";
import { useSourceLabel } from "./badges";
import { CorrelationCard } from "./correlation-card";
import { DemoReset } from "./demo-reset";
import { ErrorNotice, LoadingNote, PageHeading } from "./feedback";
import { useI18n } from "./locale-provider";
import { Seam, type SeamItem } from "./seam";
import { SourceHealthCard } from "./source-health-card";

const LATEST_COUNT = 5;

type RunState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "done"; summary: ExecutionSummary }
  | { status: "failed"; error: ApiError };

function RunResult({ run }: Readonly<{ run: RunState }>) {
  const { t, tp, locale } = useI18n();
  let content: React.ReactNode = null;
  if (run.status === "running") {
    content = <p className="text-muted">{t("dashboard.run.running")}</p>;
  } else if (run.status === "failed") {
    content = <ErrorNotice error={run.error} />;
  } else if (run.status === "done") {
    const { summary } = run;
    content =
      summary.status === "no_rules" ? (
        <p>{t("dashboard.run.noRules")}</p>
      ) : (
        <dl className="stat-row">
          <div>
            <dt>{t("dashboard.run.executed")}</dt>
            <dd className="font-mono">{formatNumber(summary.rules_executed, locale)}</dd>
          </div>
          <div>
            <dt>{t("dashboard.run.failed")}</dt>
            <dd className="font-mono" data-alert={summary.rules_failed > 0}>
              {formatNumber(summary.rules_failed, locale)}
            </dd>
          </div>
          <div>
            <dt>{t("dashboard.run.found")}</dt>
            <dd className="font-mono">{tp("dashboard.run.foundCount", summary.correlations_found)}</dd>
          </div>
          <div>
            <dt>{t("dashboard.run.duration")}</dt>
            <dd className="font-mono">{formatDuration(summary.duration_ms, locale)}</dd>
          </div>
        </dl>
      );
  }
  // The region exists before its content so each result is announced
  return (
    <div aria-live="polite" className="run-result">
      {content}
    </div>
  );
}

export function Dashboard() {
  const { t, tp, locale } = useI18n();
  const sourceLabel = useSourceLabel();
  const now = useNow();
  const sources = useResource(fetchSources);
  const counts = useResource(fetchRecordCounts);
  const rules = useResource(fetchRules);
  const live = useLiveCorrelations();
  const [run, setRun] = useState<RunState>({ status: "idle" });

  const execute = useCallback(async () => {
    // aria-disabled keeps the button focusable, so the guard lives here
    if (run.status === "running") {
      return;
    }
    setRun({ status: "running" });
    const result = await executeRules();
    setRun(result.ok ? { status: "done", summary: result.data } : { status: "failed", error: result.error });
    if (result.ok) {
      live.refresh();
      counts.reload();
    }
  }, [run.status, live, counts]);

  const reloadAfterReset = useCallback(() => {
    live.refresh();
    rules.reload();
    counts.reload();
    setRun({ status: "idle" });
  }, [live, rules, counts]);

  const sourceList = sources.state.status === "ready" ? sources.state.data : [];
  const down = unhealthySources(sourceList);
  const recordCounts = counts.state.status === "ready" ? counts.state.data : {};
  const correlations = live.state.status === "ready" ? live.state.correlations : [];
  const severityCounts = countBySeverity(correlations);
  const activeRules = rules.state.status === "ready" ? rules.state.data.filter((rule) => rule.status === "active").length : null;
  const seamItems: SeamItem[] = SOURCE_NAMES.map((name) => ({
    source: name,
    state: down.some((source) => source.name === name) ? "broken" : "joined",
  }));

  return (
    <>
      <PageHeading title={t("dashboard.title")} lead={t("dashboard.lead")} />

      {down.length > 0 && (
        <div className="notice notice-warning" role="alert">
          <p className="notice-title">{tp("dashboard.degraded.title", down.length)}</p>
          <p className="notice-text">
            {tp("dashboard.degraded.body", down.length, {
              sources: formatList(
                down.map((source) => sourceLabel(source.name)),
                locale,
              ),
            })}
          </p>
        </div>
      )}

      <section aria-labelledby="sources-heading" className="section">
        <h2 id="sources-heading" className="section-title">
          {t("dashboard.sources")}
        </h2>
        {sources.state.status === "loading" && <LoadingNote />}
        {sources.state.status === "failed" && <ErrorNotice error={sources.state.error} onRetry={sources.reload} />}
        {sources.state.status === "ready" && (
          <>
            <Seam items={seamItems} />
            <div className="card-grid">
              {SOURCE_NAMES.map((name) => {
                const source = sourceList.find((entry) => entry.name === name);
                return source === undefined ? null : (
                  <SourceHealthCard key={name} source={source} recordCount={recordCounts[name]} now={now} />
                );
              })}
            </div>
          </>
        )}
      </section>

      <section aria-labelledby="stats-heading" className="section">
        <h2 id="stats-heading" className="section-title">
          {t("dashboard.stats")}
        </h2>
        <dl className="stat-row glass-panel panel">
          <div>
            <dt>{t("dashboard.stats.activeRules")}</dt>
            <dd className="font-mono">{activeRules === null ? t("common.unknown") : formatNumber(activeRules, locale)}</dd>
          </div>
          <div>
            <dt>{t("dashboard.stats.correlations")}</dt>
            <dd className="font-mono">{formatNumber(correlations.length, locale)}</dd>
          </div>
          <div>
            <dt>{t("severity.warning")}</dt>
            <dd className="font-mono">{formatNumber(severityCounts.warning, locale)}</dd>
          </div>
          <div>
            <dt>{t("severity.error")}</dt>
            <dd className="font-mono">{formatNumber(severityCounts.error, locale)}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="run-heading" className="section">
        <h2 id="run-heading" className="section-title">
          {t("dashboard.run.title")}
        </h2>
        <p className="text-secondary">{t("dashboard.run.hint")}</p>
        <div className="button-row">
          <button type="button" className="button button-primary" aria-disabled={run.status === "running"} onClick={() => void execute()}>
            {run.status === "running" ? t("dashboard.run.running") : t("dashboard.run.button")}
          </button>
        </div>
        <RunResult run={run} />
      </section>

      <section aria-labelledby="latest-heading" className="section">
        <div className="section-head">
          <h2 id="latest-heading" className="section-title">
            {t("dashboard.latest")}
          </h2>
          <Link href="/correlations" className="text-link">
            {t("dashboard.latest.all")}
          </Link>
        </div>
        {live.state.status === "loading" && <LoadingNote />}
        {live.state.status === "failed" && <ErrorNotice error={live.state.error} onRetry={live.refresh} />}
        {live.state.status === "ready" && correlations.length === 0 && (
          <p className="text-secondary">{t("correlations.empty")}</p>
        )}
        <div className="card-stack">
          {correlations.slice(0, LATEST_COUNT).map((correlation) => (
            <CorrelationCard key={correlation.id} correlation={correlation} now={now} />
          ))}
        </div>
      </section>

      <DemoReset onDone={reloadAfterReset} />

      <ApiStatus />
    </>
  );
}
