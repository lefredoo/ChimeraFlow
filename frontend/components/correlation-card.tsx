"use client";

import { useId, useState } from "react";

import type { Correlation } from "../lib/api-types";
import { contributingSources } from "../lib/correlations/filter";
import { formatDateTime, formatRelativeTime } from "../lib/format";
import { SeverityBadge } from "./badges";
import { ExplanationPanel } from "./explanation-panel";
import { useI18n } from "./locale-provider";
import { ProvenanceDrawer } from "./provenance-drawer";
import { Seam } from "./seam";

/**
 * One correlation. `message` and every provenance field come from source
 * files (WhatsApp text, spreadsheet cells): they are rendered as React text
 * only, never as HTML (security rule R12).
 */
export function CorrelationCard({ correlation, now }: Readonly<{ correlation: Correlation; now: number }>) {
  const { t, tp, locale } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [explanationOpen, setExplanationOpen] = useState(false);
  const explanationId = useId();

  const relative = formatRelativeTime(correlation.detected_at, now, locale);
  const absolute = formatDateTime(correlation.detected_at, locale);
  const { explanation } = correlation;
  const hasExplanation = explanation !== undefined && explanation !== null;
  const sources = contributingSources(correlation.provenance);

  return (
    <article className="correlation-card glass-panel" data-severity={correlation.severity}>
      <header className="correlation-header">
        <SeverityBadge severity={correlation.severity} />
        <span className="font-mono correlation-rule">{correlation.rule_id}</span>
        {relative !== null && absolute !== null && (
          <time className="text-muted correlation-time" dateTime={correlation.detected_at} title={absolute}>
            {relative}
          </time>
        )}
      </header>
      <p className="correlation-message">{correlation.message}</p>
      {sources.length > 0 && <Seam items={sources.map((source) => ({ source, state: "joined" }))} />}
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={() => setDrawerOpen(true)}>
          {tp("correlation.provenance", correlation.provenance.length)}
        </button>
        {hasExplanation && (
          <button
            type="button"
            className="button button-secondary"
            aria-expanded={explanationOpen}
            aria-controls={explanationId}
            onClick={() => setExplanationOpen((value) => !value)}
          >
            {t("correlation.why")}
          </button>
        )}
      </div>
      {hasExplanation && (
        <div id={explanationId} hidden={!explanationOpen}>
          {explanationOpen && <ExplanationPanel explanation={explanation} />}
        </div>
      )}
      {drawerOpen && <ProvenanceDrawer correlation={correlation} onClose={() => setDrawerOpen(false)} />}
    </article>
  );
}
