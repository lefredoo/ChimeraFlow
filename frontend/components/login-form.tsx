"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState, type FormEvent } from "react";

import { DEMO_LOGIN_EMAIL, DEMO_LOGIN_PASSWORD } from "../lib/demo-credentials";
import type { MessageKey } from "../lib/i18n";
import type { LoginResult } from "../lib/services/auth-service";
import { useAuth } from "./auth-provider";
import { useI18n } from "./locale-provider";

const HOME_PATH = "/";

function errorMessage(
  result: Exclude<LoginResult, { state: "success" }>,
  t: ReturnType<typeof useI18n>["t"],
): string {
  const keys: Record<Exclude<LoginResult["state"], "success" | "rate_limited">, MessageKey> = {
    invalid_credentials: "login.error.invalid",
    unreachable: "login.error.unreachable",
    error: "login.error.generic",
  };
  if (result.state === "rate_limited") {
    return result.retryAfterSeconds === undefined
      ? t("login.error.rateLimitedNoDelay")
      : t("login.error.rateLimited", { seconds: result.retryAfterSeconds });
  }
  return t(keys[result.state]);
}

export function LoginForm() {
  const { state, signIn } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const ids = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (state.status === "authenticated") {
      router.replace(HOME_PATH);
    }
  }, [state.status, router]);

  async function submit(emailValue: string, passwordValue: string) {
    // aria-disabled keeps the button focusable, so the guard lives here
    if (submitting) {
      return;
    }
    setSubmitting(true);
    setError("");
    const result = await signIn(emailValue, passwordValue);
    setSubmitting(false);
    if (result.state !== "success") {
      setError(errorMessage(result, t));
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(email, password);
  }

  function handleDemo() {
    setEmail(DEMO_LOGIN_EMAIL);
    setPassword(DEMO_LOGIN_PASSWORD);
    void submit(DEMO_LOGIN_EMAIL, DEMO_LOGIN_PASSWORD);
  }

  const emailId = `${ids}-email`;
  const passwordId = `${ids}-password`;
  const errorId = `${ids}-error`;
  const credentialsId = `${ids}-credentials`;
  const describedBy = error === "" ? undefined : errorId;

  return (
    <div className="login-stack">
      <section className="glass-panel panel" aria-labelledby={`${ids}-demo-heading`}>
        <h2 id={`${ids}-demo-heading`} className="panel-subtitle">
          {t("login.demo.heading")}
        </h2>
        <p className="text-secondary">{t("login.demo.description")}</p>
        {/* Revealed on click only: the credentials are not in the prerendered HTML that bots scrape */}
        <div id={credentialsId}>
          {revealed ? (
            <dl className="credentials">
              <div className="credentials-row">
                <dt className="status-label">{t("login.demo.email")}</dt>
                <dd className="font-mono">{DEMO_LOGIN_EMAIL}</dd>
              </div>
              <div className="credentials-row">
                <dt className="status-label">{t("login.demo.password")}</dt>
                <dd className="font-mono">{DEMO_LOGIN_PASSWORD}</dd>
              </div>
            </dl>
          ) : null}
        </div>
        <div className="button-row">
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setRevealed((value) => !value)}
            aria-expanded={revealed}
            aria-controls={credentialsId}
          >
            {revealed ? t("login.demo.hide") : t("login.demo.reveal")}
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={handleDemo}
            aria-disabled={submitting}
          >
            {t("login.demo.button")}
          </button>
        </div>
      </section>

      <section className="glass-panel panel" aria-labelledby={`${ids}-form-heading`}>
        <h2 id={`${ids}-form-heading`} className="panel-subtitle">
          {t("login.form.heading")}
        </h2>
        <form onSubmit={handleSubmit} aria-busy={submitting} className="form">
          <div className="form-field">
            <label htmlFor={emailId} className="form-label">
              {t("login.email.label")}
            </label>
            <input
              id={emailId}
              className="form-input"
              type="email"
              name="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={error !== ""}
              aria-describedby={describedBy}
            />
          </div>
          <div className="form-field">
            <label htmlFor={passwordId} className="form-label">
              {t("login.password.label")}
            </label>
            <input
              id={passwordId}
              className="form-input"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={error !== ""}
              aria-describedby={describedBy}
            />
          </div>
          {/* Always mounted: a live region must exist before its text changes to be announced */}
          <p id={errorId} className="form-error" role="alert">
            {error}
          </p>
          <button type="submit" className="button button-primary" aria-disabled={submitting}>
            {submitting ? t("login.submitting") : t("login.submit")}
          </button>
        </form>
      </section>
    </div>
  );
}
