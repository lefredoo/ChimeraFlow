"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";

import type { Language, Rule, RuleConversion } from "../lib/api-types";
import { COMPOSER_MAX_LENGTH, COMPOSER_MIN_LENGTH, validateComposerText } from "../lib/composer";
import type { ApiError } from "../lib/services/http";
import { convertText, createRule } from "../lib/services/rules-service";
import { RuleStatusBadge } from "./badges";
import { ErrorNotice, PageHeading } from "./feedback";
import { useI18n } from "./locale-provider";
import { RuleJson } from "./rule-json";
import { RuleSummary } from "./rule-summary";

function Suggestions({ rules, onPick }: Readonly<{ rules: readonly Rule[]; onPick: (rule: Rule) => void }>) {
  const { t, tp } = useI18n();
  if (rules.length === 0) {
    return null;
  }
  return (
    <section className="notice" aria-labelledby="suggestions-heading">
      <h2 id="suggestions-heading" className="panel-subtitle">
        {t("composer.suggestions.title")}
      </h2>
      <p className="text-secondary">{tp("composer.suggestions.hint", rules.length)}</p>
      <ul className="suggestion-list">
        {rules.map((rule) => (
          <li key={rule.id}>
            <button type="button" className="suggestion" onClick={() => onPick(rule)}>
              <span className="font-mono suggestion-id">{rule.id}</span>
              <RuleStatusBadge status={rule.status} />
              <span className="suggestion-text">{rule.natural_language}</span>
            </button>
          </li>
        ))}
      </ul>
      <Link href="/rules" className="text-link">
        {t("composer.suggestions.link")}
      </Link>
    </section>
  );
}

export function RuleComposer() {
  const { t, tp, locale } = useI18n();
  const router = useRouter();
  const ids = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<Language>(locale);
  const [converting, setConverting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<RuleConversion | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [showValidation, setShowValidation] = useState(false);

  const validation = validateComposerText(text);
  const length = text.trim().length;
  const fallbackRules = error !== null && error.kind === "http" ? error.fallbackRules : [];

  async function convert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // aria-disabled keeps the button focusable, so the guard lives here
    if (converting) {
      return;
    }
    if (validation !== "ok") {
      setShowValidation(true);
      textareaRef.current?.focus();
      return;
    }
    setConverting(true);
    setError(null);
    setDraft(null);
    const result = await convertText(text.trim(), language);
    setConverting(false);
    if (result.ok) {
      setDraft(result.data);
    } else {
      setError(result.error);
    }
  }

  async function save() {
    if (draft === null || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    const result = await createRule(draft.rule);
    setSaving(false);
    if (result.ok) {
      router.push("/rules");
    } else {
      setError(result.error);
    }
  }

  function pickSuggestion(rule: Rule) {
    setText(rule.natural_language.slice(0, COMPOSER_MAX_LENGTH));
    setShowValidation(false);
    textareaRef.current?.focus();
  }

  const textId = `${ids}-text`;
  const hintId = `${ids}-hint`;
  const languageId = `${ids}-language`;
  const invalid = showValidation && validation !== "ok";
  const validationMessage =
    validation === "too_short"
      ? t("composer.error.tooShort", { min: COMPOSER_MIN_LENGTH })
      : t("composer.error.tooLong", { max: COMPOSER_MAX_LENGTH });

  return (
    <>
      <PageHeading title={t("composer.title")} lead={t("composer.lead")} />

      <form className="glass-panel panel form" onSubmit={(event) => void convert(event)} aria-busy={converting}>
        <div className="form-field">
          <label htmlFor={textId} className="form-label">
            {t("composer.text.label")}
          </label>
          <textarea
            id={textId}
            ref={textareaRef}
            className="form-input form-textarea"
            rows={5}
            value={text}
            onChange={(event) => setText(event.target.value)}
            aria-invalid={invalid}
            aria-describedby={hintId}
            placeholder={t("composer.text.placeholder")}
          />
          <p id={hintId} className="form-hint">
            <span>{t("composer.text.hint", { min: COMPOSER_MIN_LENGTH, max: COMPOSER_MAX_LENGTH })}</span>
            <span className="font-mono counter" data-over={length > COMPOSER_MAX_LENGTH}>
              {length}/{COMPOSER_MAX_LENGTH}
            </span>
          </p>
          <p className="form-error" role="alert">
            {invalid ? validationMessage : ""}
          </p>
        </div>
        <div className="form-field">
          <label htmlFor={languageId} className="form-label">
            {t("composer.language.label")}
          </label>
          <select
            id={languageId}
            className="form-input form-select"
            value={language}
            onChange={(event) => setLanguage(event.target.value === "en" ? "en" : "fr")}
          >
            <option value="fr">{t("locale.fr")}</option>
            <option value="en">{t("locale.en")}</option>
          </select>
        </div>
        <div className="button-row">
          <button type="submit" className="button button-primary" aria-disabled={converting}>
            {converting ? t("composer.submitting") : t("composer.submit")}
          </button>
        </div>
      </form>

      {error !== null && (
        <>
          <ErrorNotice error={error} />
          <Suggestions rules={fallbackRules} onPick={pickSuggestion} />
        </>
      )}

      <div aria-live="polite">
        {draft !== null && (
          <section className="glass-panel panel section" aria-labelledby={`${ids}-draft`}>
            <h2 id={`${ids}-draft`} className="section-title">
              {t("composer.draft.title")}
            </h2>
            <p>{t("composer.draft.review")}</p>
            <p className="text-muted">{tp("composer.draft.retries", draft.retries)}</p>
            <h3 className="drawer-subtitle">{t("rules.detail.summary")}</h3>
            <RuleSummary rule={draft.rule} />
            <h3 className="drawer-subtitle">{t("rules.detail.json")}</h3>
            <RuleJson rule={draft.rule} />
            <div className="button-row">
              <button type="button" className="button button-primary" aria-disabled={saving} onClick={() => void save()}>
                {saving ? t("composer.saving") : t("composer.save")}
              </button>
              <button type="button" className="button button-secondary" onClick={() => setDraft(null)}>
                {t("composer.discard")}
              </button>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
