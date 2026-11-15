import type { Metadata } from "next";

import { LoginForm } from "../../components/login-form";
import { t } from "../../lib/i18n";

export const metadata: Metadata = {
  title: t("login.meta.title"),
};

export default function LoginPage() {
  return (
    <main className="page">
      <div className="page-content login-content">
        <header className="hero">
          <h1 className="hero-title font-display">{t("login.title")}</h1>
          <p className="hero-tagline">{t("login.subtitle")}</p>
        </header>
        <LoginForm />
      </div>
    </main>
  );
}
