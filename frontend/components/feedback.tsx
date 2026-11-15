"use client";

import { describeApiError } from "../lib/error-messages";
import type { ApiError } from "../lib/services/http";
import { useI18n } from "./locale-provider";

/** The message for an API failure, announced to screen readers, with an optional retry. */
export function ErrorNotice({ error, onRetry }: Readonly<{ error: ApiError; onRetry?: () => void }>) {
  const { t } = useI18n();
  const message = describeApiError(error);
  return (
    <div className="notice notice-error" role="alert">
      <p className="notice-text">{t(message.key, message.params)}</p>
      {onRetry !== undefined && (
        <button type="button" className="button button-secondary" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

/** Loading placeholder, announced politely. */
export function LoadingNote() {
  const { t } = useI18n();
  return (
    <p className="text-muted" role="status">
      {t("common.loading")}
    </p>
  );
}

/** Heading of a page: title and one line of purpose. */
export function PageHeading({ title, lead }: Readonly<{ title: string; lead: string }>) {
  return (
    <header className="page-heading">
      <h1 className="page-title font-display">{title}</h1>
      <p className="text-secondary page-lead">{lead}</p>
      <div className="seam-line" aria-hidden="true" />
    </header>
  );
}
