"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "./auth-provider";
import { useI18n } from "./locale-provider";

export const LOGIN_PATH = "/login";

/**
 * Render the children only for a signed-in user; send everyone else to the
 * login page. While the session is being checked, a status message is shown
 * instead of the protected content.
 */
export function RequireAuth({ children }: Readonly<{ children: React.ReactNode }>) {
  const { state } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (state.status === "anonymous") {
      router.replace(LOGIN_PATH);
    }
  }, [state.status, router]);

  if (state.status !== "authenticated") {
    return (
      <main className="page">
        <p className="text-muted" role="status">
          {t("auth.checking")}
        </p>
      </main>
    );
  }
  return <>{children}</>;
}
