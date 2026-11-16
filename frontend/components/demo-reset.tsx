"use client";

import { useState } from "react";

import { resetDemo, type DemoResetSummary } from "../lib/services/demo-service";
import type { ApiError } from "../lib/services/http";
import { ErrorNotice } from "./feedback";
import { useI18n } from "./locale-provider";
import { ModalDialog } from "./modal-dialog";

type ResetState =
  | { status: "idle" }
  | { status: "confirming" }
  | { status: "pending" }
  | { status: "done"; summary: DemoResetSummary }
  | { status: "unavailable" }
  | { status: "failed"; error: ApiError };

/** Puts the shared demo back in its shipped state, after a confirmation. */
export function DemoReset({ onDone }: Readonly<{ onDone: () => void }>) {
  const { t, locale } = useI18n();
  const [state, setState] = useState<ResetState>({ status: "idle" });

  async function confirm() {
    if (state.status === "pending") {
      return;
    }
    setState({ status: "pending" });
    const result = await resetDemo();
    if (result.ok) {
      setState({ status: "done", summary: result.data });
      onDone();
    } else if (result.error.kind === "http" && result.error.status === 404) {
      setState({ status: "unavailable" });
    } else {
      setState({ status: "failed", error: result.error });
    }
  }

  const dialogOpen = state.status === "confirming" || state.status === "pending";
  const number = new Intl.NumberFormat(locale);

  return (
    <section aria-labelledby="demo-heading" className="section">
      <h2 id="demo-heading" className="section-title">
        {t("demo.title")}
      </h2>
      <p className="text-secondary">{t("demo.hint")}</p>
      <div className="button-row">
        <button type="button" className="button button-secondary" onClick={() => setState({ status: "confirming" })}>
          {t("demo.button")}
        </button>
      </div>
      <div aria-live="polite">
        {state.status === "done" && (
          <p>
            {t("demo.done", {
              correlations: number.format(state.summary.correlationsDeleted),
              executions: number.format(state.summary.executionsDeleted),
            })}
          </p>
        )}
        {state.status === "unavailable" && <p className="text-secondary">{t("demo.unavailable")}</p>}
        {state.status === "failed" && <ErrorNotice error={state.error} />}
      </div>
      {dialogOpen && (
        <ModalDialog title={t("demo.confirm.title")} onClose={() => setState({ status: "idle" })} variant="confirm">
          <p>{t("demo.confirm.question")}</p>
          <div className="button-row">
            <button type="button" className="button button-secondary" onClick={() => setState({ status: "idle" })}>
              {t("common.cancel")}
            </button>
            <button
              type="button"
              className="button button-danger"
              aria-disabled={state.status === "pending"}
              onClick={() => void confirm()}
            >
              {state.status === "pending" ? t("demo.pending") : t("demo.confirm.button")}
            </button>
          </div>
        </ModalDialog>
      )}
    </section>
  );
}
