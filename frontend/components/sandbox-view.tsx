"use client";

import { useId, useRef, useState, type FormEvent } from "react";

import type { NormalizedForms, NormalizeResult } from "../lib/api-types";
import type { MessageKey } from "../lib/i18n";
import {
  CIMENT_SIZES,
  CIMENT_VARIANTS,
  formatScore,
  parseSandboxInput,
  SANDBOX_MAX_COMPARISONS,
  SANDBOX_MAX_TEXT_LENGTH,
} from "../lib/sandbox";
import type { ApiError } from "../lib/services/http";
import { normalizeText } from "../lib/services/normalize-service";
import { ErrorNotice, PageHeading } from "./feedback";
import { useI18n } from "./locale-provider";

type SandboxState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; result: NormalizeResult }
  | { status: "unavailable" }
  | { status: "failed"; error: ApiError };

const METHOD_KEYS: Record<string, MessageKey> = {
  exact: "sandbox.method.exact",
  synonym: "sandbox.method.synonym",
  fuzzy: "sandbox.method.fuzzy",
  token: "sandbox.method.token",
};

function listOrNone(items: readonly string[], separator: string, none: string): string {
  return items.length === 0 ? none : items.join(separator);
}

function Reference({ forms }: Readonly<{ forms: NormalizedForms }>) {
  const { t } = useI18n();
  return (
    <section className="glass-panel panel section" aria-labelledby="reference-heading">
      <h2 id="reference-heading" className="section-title">
        {t("sandbox.reference")}
      </h2>
      <dl className="meta-list">
        <div>
          <dt>{t("sandbox.col.text")}</dt>
          <dd className="font-mono">{forms.text}</dd>
        </div>
        <div>
          <dt>{t("sandbox.col.key")}</dt>
          <dd className="font-mono">{forms.norm}</dd>
        </div>
        <div>
          <dt>{t("sandbox.col.canonical")}</dt>
          <dd className="font-mono">{forms.canonical}</dd>
        </div>
        <div>
          <dt>{t("sandbox.col.tokens")}</dt>
          <dd className="font-mono">{listOrNone(forms.tokens, " · ", t("common.none"))}</dd>
        </div>
        <div>
          <dt>{t("sandbox.col.numbers")}</dt>
          <dd className="font-mono">{listOrNone(forms.numbers, ", ", t("common.none"))}</dd>
        </div>
      </dl>
    </section>
  );
}

function Comparisons({ result }: Readonly<{ result: NormalizeResult }>) {
  const { t, locale } = useI18n();
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={t("sandbox.results.comparisons")}>
      <table className="data-table">
        <caption className="sr-only">{t("sandbox.results.comparisons")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("sandbox.col.text")}</th>
            <th scope="col">{t("sandbox.col.key")}</th>
            <th scope="col">{t("sandbox.col.numbers")}</th>
            <th scope="col">{t("sandbox.col.score")}</th>
            <th scope="col">{t("sandbox.col.verdict")}</th>
          </tr>
        </thead>
        <tbody>
          {result.comparisons.map((comparison, index) => {
            const methodKey = comparison.method === null ? undefined : METHOD_KEYS[comparison.method];
            return (
              // The same text can be typed twice: the position is the identity
              <tr key={index} data-matched={comparison.matched}>
                <th scope="row" className="font-mono">
                  {comparison.text}
                </th>
                <td className="font-mono">{comparison.norm}</td>
                <td className="font-mono">{listOrNone(comparison.numbers, ", ", t("common.none"))}</td>
                <td className="font-mono score-cell">
                  <meter min={0} max={1} value={comparison.score} aria-hidden="true" />
                  {formatScore(comparison.score, locale)}
                </td>
                <td>
                  <span className="verdict" data-matched={comparison.matched}>
                    {comparison.matched ? t("sandbox.verdict.match") : t("sandbox.verdict.noMatch")}
                  </span>
                  {comparison.method !== null && (
                    <span className="text-muted verdict-method">
                      {methodKey === undefined ? comparison.method : t(methodKey)}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SandboxView() {
  const { t, tp } = useI18n();
  const ids = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [raw, setRaw] = useState("");
  const [state, setState] = useState<SandboxState>({ status: "idle" });
  const [inputError, setInputError] = useState<"empty" | "too_many" | "too_long" | null>(null);

  async function analyze(value: string) {
    // aria-disabled keeps the buttons focusable, so the guard lives here
    if (state.status === "loading") {
      return;
    }
    const parsed = parseSandboxInput(value);
    if (!parsed.ok) {
      setInputError(parsed.reason);
      textareaRef.current?.focus();
      return;
    }
    setInputError(null);
    setState({ status: "loading" });
    const result = await normalizeText(parsed.text, parsed.compareWith);
    if (result.ok) {
      setState({ status: "ready", result: result.data });
    } else if (result.error.kind === "http" && (result.error.status === 404 || result.error.status === 405)) {
      setState({ status: "unavailable" });
    } else {
      setState({ status: "failed", error: result.error });
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void analyze(raw);
  }

  function loadExample(texts: readonly string[]) {
    const value = texts.join("\n");
    setRaw(value);
    void analyze(value);
  }

  const textId = `${ids}-text`;
  const hintId = `${ids}-hint`;
  const inputMessage =
    inputError === "empty"
      ? t("sandbox.error.empty")
      : inputError === "too_many"
        ? t("sandbox.error.tooMany", { max: SANDBOX_MAX_COMPARISONS + 1 })
        : inputError === "too_long"
          ? t("sandbox.error.tooLong", { max: SANDBOX_MAX_TEXT_LENGTH })
          : "";

  return (
    <>
      <PageHeading title={t("sandbox.title")} lead={t("sandbox.lead")} />

      <form className="glass-panel panel form" onSubmit={submit} aria-busy={state.status === "loading"}>
        <div className="form-field">
          <label htmlFor={textId} className="form-label">
            {t("sandbox.text.label")}
          </label>
          <textarea
            id={textId}
            ref={textareaRef}
            className="form-input form-textarea font-mono"
            rows={5}
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            aria-invalid={inputError !== null}
            aria-describedby={hintId}
          />
          <p id={hintId} className="form-hint">
            {t("sandbox.text.hint", { max: SANDBOX_MAX_COMPARISONS })}
          </p>
          <p className="form-error" role="alert">
            {inputMessage}
          </p>
        </div>
        <div className="button-row">
          <button type="submit" className="button button-primary" aria-disabled={state.status === "loading"}>
            {state.status === "loading" ? t("sandbox.submitting") : t("sandbox.submit")}
          </button>
          <button type="button" className="button button-secondary" onClick={() => loadExample(CIMENT_VARIANTS)}>
            {t("sandbox.example.variants")}
          </button>
          <button type="button" className="button button-secondary" onClick={() => loadExample(CIMENT_SIZES)}>
            {t("sandbox.example.sizes")}
          </button>
        </div>
      </form>

      <div aria-live="polite" className="section">
        {state.status === "unavailable" && (
          <div className="notice notice-warning">
            <p className="notice-title">{t("sandbox.unavailable.title")}</p>
            <p className="notice-text">{t("sandbox.unavailable.body")}</p>
          </div>
        )}
        {state.status === "failed" && <ErrorNotice error={state.error} />}
        {state.status === "ready" && (
          <>
            <Reference forms={state.result} />
            {state.result.comparisons.length === 0 ? (
              <p className="text-muted">{t("sandbox.results.noComparison")}</p>
            ) : (
              <>
                <p className="text-muted">{tp("sandbox.results.count", state.result.comparisons.length)}</p>
                <Comparisons result={state.result} />
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}
