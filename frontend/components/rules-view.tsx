"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { useResource } from "../hooks/use-resource";
import { SOURCE_NAMES, type Rule } from "../lib/api-types";
import type { ApiError } from "../lib/services/http";
import { deleteRule, fetchPredefinedRules, fetchRules } from "../lib/services/rules-service";
import { RuleStatusBadge } from "./badges";
import { ErrorNotice, LoadingNote, PageHeading } from "./feedback";
import { useI18n } from "./locale-provider";
import { ModalDialog } from "./modal-dialog";
import { RuleJson } from "./rule-json";
import { RuleSummary } from "./rule-summary";
import { Seam } from "./seam";

function ruleSources(rule: Rule) {
  const used = new Set([rule.trigger.source, ...rule.joins.map((join) => join.source)]);
  return SOURCE_NAMES.filter((name) => used.has(name)).map((source) => ({ source, state: "joined" as const }));
}

function DeleteDialog({
  rule,
  onClose,
  onDeleted,
}: Readonly<{ rule: Rule; onClose: () => void; onDeleted: () => void }>) {
  const { t } = useI18n();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function confirm() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    const result = await deleteRule(rule.id);
    setPending(false);
    if (result.ok) {
      onDeleted();
    } else if (result.error.kind === "http" && result.error.status === 404) {
      // Already gone elsewhere: the list only needs a refresh
      onDeleted();
    } else {
      setError(result.error);
    }
  }

  return (
    <ModalDialog title={t("rules.delete.title")} onClose={onClose} variant="confirm">
      <p>{t("rules.delete.question", { id: rule.id })}</p>
      <p className="text-muted">{t("rules.delete.hint")}</p>
      {error !== null && <ErrorNotice error={error} />}
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onClose}>
          {t("common.cancel")}
        </button>
        <button type="button" className="button button-danger" aria-disabled={pending} onClick={() => void confirm()}>
          {pending ? t("rules.delete.pending") : t("rules.delete.confirm")}
        </button>
      </div>
    </ModalDialog>
  );
}

function RuleCard({
  rule,
  predefined,
  onDetails,
  onDelete,
}: Readonly<{ rule: Rule; predefined: boolean; onDetails: () => void; onDelete: () => void }>) {
  const { t, tp } = useI18n();
  return (
    <article className="rule-card glass-panel" data-status={rule.status}>
      <header className="rule-card-header">
        <h3 className="rule-id font-mono">{rule.id}</h3>
        <RuleStatusBadge status={rule.status} />
        <span className="origin-badge">{predefined ? t("rules.origin.predefined") : t("rules.origin.custom")}</span>
      </header>
      <p className="rule-text">{rule.natural_language}</p>
      <Seam items={ruleSources(rule)} />
      <p className="text-muted">{tp("rules.joinsCount", rule.joins.length)}</p>
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={onDetails}>
          {t("rules.details")}
        </button>
        <button type="button" className="button button-secondary" onClick={onDelete}>
          {t("rules.delete.button")}
        </button>
      </div>
    </article>
  );
}

export function RulesView() {
  const { t, tp } = useI18n();
  const rules = useResource(fetchRules);
  const predefined = useResource(fetchPredefinedRules);
  const [detail, setDetail] = useState<Rule | null>(null);
  const [toDelete, setToDelete] = useState<Rule | null>(null);

  const predefinedIds = useMemo(
    () => new Set(predefined.state.status === "ready" ? predefined.state.data.map((rule) => rule.id) : []),
    [predefined.state],
  );

  const afterDelete = useCallback(() => {
    setToDelete(null);
    rules.reload();
  }, [rules]);

  return (
    <>
      <PageHeading title={t("rules.title")} lead={t("rules.lead")} />
      <div className="button-row">
        <Link href="/rules/new" className="button button-primary">
          {t("rules.new")}
        </Link>
      </div>

      {rules.state.status === "loading" && <LoadingNote />}
      {rules.state.status === "failed" && <ErrorNotice error={rules.state.error} onRetry={rules.reload} />}
      {rules.state.status === "ready" && (
        <section aria-labelledby="rules-count" className="section">
          <h2 id="rules-count" className="section-title">
            {tp("rules.count", rules.state.data.length)}
          </h2>
          {rules.state.data.length === 0 && <p className="text-secondary">{t("rules.empty")}</p>}
          <div className="card-stack">
            {rules.state.data.map((rule) => (
              <RuleCard
                key={rule.id}
                rule={rule}
                predefined={predefinedIds.has(rule.id)}
                onDetails={() => setDetail(rule)}
                onDelete={() => setToDelete(rule)}
              />
            ))}
          </div>
        </section>
      )}

      {detail !== null && (
        <ModalDialog title={t("rules.detail.title", { id: detail.id })} onClose={() => setDetail(null)} variant="drawer">
          <p className="rule-text">{detail.natural_language}</p>
          <h3 className="drawer-subtitle">{t("rules.detail.summary")}</h3>
          <RuleSummary rule={detail} />
          <h3 className="drawer-subtitle">{t("rules.detail.json")}</h3>
          <RuleJson rule={detail} />
        </ModalDialog>
      )}
      {toDelete !== null && <DeleteDialog rule={toDelete} onClose={() => setToDelete(null)} onDeleted={afterDelete} />}
    </>
  );
}
