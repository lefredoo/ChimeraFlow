"use client";

import { PreferencesRow } from "./app-shell";
import { LoginForm } from "./login-form";
import { useI18n } from "./locale-provider";

export function LoginView() {
  const { t } = useI18n();
  return (
    <main className="page">
      <div className="page-content login-content">
        <PreferencesRow />
        <header className="hero">
          <h1 className="hero-title font-display">{t("login.title")}</h1>
          <p className="hero-tagline">{t("login.subtitle")}</p>
        </header>
        <LoginForm />
      </div>
    </main>
  );
}
