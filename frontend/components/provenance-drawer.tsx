"use client";

import type { Correlation } from "../lib/api-types";
import { formatDateTime } from "../lib/format";
import { SourceBadge } from "./badges";
import { useI18n } from "./locale-provider";
import { ModalDialog } from "./modal-dialog";

/** Where each record behind a correlation comes from (source, position in the file, record id). */
export function ProvenanceDrawer({
  correlation,
  onClose,
}: Readonly<{ correlation: Correlation; onClose: () => void }>) {
  const { t, tp, locale } = useI18n();
  const detectedAt = formatDateTime(correlation.detected_at, locale);
  return (
    <ModalDialog title={t("provenance.title")} onClose={onClose} variant="drawer">
      <p className="correlation-message">{correlation.message}</p>
      <dl className="meta-list">
        <div>
          <dt>{t("provenance.rule")}</dt>
          <dd className="font-mono">{correlation.rule_id}</dd>
        </div>
        {detectedAt !== null && (
          <div>
            <dt>{t("provenance.detectedAt")}</dt>
            <dd>{detectedAt}</dd>
          </div>
        )}
      </dl>
      <h3 className="drawer-subtitle">{tp("provenance.records", correlation.provenance.length)}</h3>
      {correlation.provenance.length === 0 ? (
        <p className="text-muted">{t("provenance.empty")}</p>
      ) : (
        <ol className="provenance-list">
          {correlation.provenance.map((entry) => (
            <li key={`${entry.source}:${entry.source_ref}:${entry.record_id}`} className="provenance-item">
              <SourceBadge source={entry.source} />
              <dl className="meta-list">
                <div>
                  <dt>{t("provenance.sourceRef")}</dt>
                  <dd className="font-mono">{entry.source_ref}</dd>
                </div>
                <div>
                  <dt>{t("provenance.recordId")}</dt>
                  <dd className="font-mono">{entry.record_id}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ol>
      )}
    </ModalDialog>
  );
}
