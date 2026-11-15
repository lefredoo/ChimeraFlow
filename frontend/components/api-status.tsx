"use client";

import { useEffect, useState } from "react";

import type { MessageKey } from "../lib/i18n";
import { fetchHealth, type HealthResult } from "../lib/services/health-service";
import { useI18n } from "./locale-provider";

type HealthState = HealthResult | { state: "checking" };

const STATUS_LABEL_KEYS: Record<HealthState["state"], MessageKey> = {
  checking: "status.checking",
  connected: "status.connected",
  error: "status.error",
  unreachable: "status.unreachable",
};

/** One line with the backend's liveness and version. */
export function ApiStatus() {
  const { t } = useI18n();
  const [health, setHealth] = useState<HealthState>({ state: "checking" });

  useEffect(() => {
    let cancelled = false;
    void fetchHealth().then((result) => {
      if (!cancelled) {
        setHealth(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <p className="api-status text-muted" data-state={health.state} role="status">
      {t("status.summary", { state: t(STATUS_LABEL_KEYS[health.state]) })}
      {health.state === "connected" && health.version !== undefined && (
        <span className="font-mono api-version">{t("status.versionValue", { version: health.version })}</span>
      )}
    </p>
  );
}
