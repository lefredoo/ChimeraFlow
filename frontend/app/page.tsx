"use client";

import { useEffect, useState } from "react";

import { FeatureCard } from "../components/feature-card";
import { RequireAuth } from "../components/require-auth";
import { UserBar } from "../components/user-bar";
import { t } from "../lib/i18n";
import { fetchHealth, type HealthResult } from "../lib/services/health-service";

type HealthState = HealthResult | { state: "checking" };

const STATUS_LABEL_KEYS = {
  checking: "status.checking",
  connected: "status.connected",
  error: "status.error",
  unreachable: "status.unreachable",
} as const;

function Dashboard() {
  const [health, setHealth] = useState<HealthState>({ state: "checking" });

  useEffect(() => {
    let cancelled = false;
    fetchHealth().then((result) => {
      if (!cancelled) {
        setHealth(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const version = health.state === "connected" ? health.version : undefined;

  return (
    <main className="page">
      <div className="page-content">
        <UserBar />
        <header className="hero">
          <h1 className="hero-title font-display">{t("home.title")}</h1>
          <p className="hero-tagline">{t("home.tagline")}</p>
          <p className="text-muted">{t("home.event")}</p>
        </header>

        <section className="glass-panel panel" aria-labelledby="api-status-heading">
          <h2 id="api-status-heading" className="panel-title">
            {t("status.heading")}
          </h2>
          <div className="status-list">
            <div className="status-row">
              <span className="status-label font-mono">{t("status.backend")}</span>
              <span className="status-value" data-state={health.state} role="status">
                {t(STATUS_LABEL_KEYS[health.state])}
              </span>
            </div>
            {version !== undefined && (
              <div className="status-row">
                <span className="status-label font-mono">{t("status.version")}</span>
                <span className="status-version font-mono">{version}</span>
              </div>
            )}
          </div>
        </section>

        <section className="feature-grid">
          <FeatureCard
            title={t("sources.excel.title")}
            description={t("sources.excel.description")}
            icon="📊"
          />
          <FeatureCard
            title={t("sources.access.title")}
            description={t("sources.access.description")}
            icon="🗄️"
          />
          <FeatureCard
            title={t("sources.whatsapp.title")}
            description={t("sources.whatsapp.description")}
            icon="💬"
          />
        </section>

        <section className="glass-panel panel">
          <h3 className="panel-subtitle">{t("phase.title")}</h3>
          <p className="text-secondary">{t("phase.summary")}</p>
          <span className="badge">{t("phase.badge")}</span>
        </section>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <RequireAuth>
      <Dashboard />
    </RequireAuth>
  );
}
