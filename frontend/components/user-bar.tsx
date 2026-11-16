"use client";

import { useAuth } from "./auth-provider";
import { useI18n } from "./locale-provider";

/** Signed-in account and sign-out button. Renders nothing when nobody is signed in. */
export function UserBar() {
  const { state, signOut } = useAuth();
  const { t } = useI18n();
  if (state.status !== "authenticated") {
    return null;
  }
  return (
    <div className="user-bar">
      <span className="text-muted user-email">{t("auth.signedInAs", { email: state.email })}</span>
      <button type="button" className="button button-secondary" onClick={signOut}>
        {t("auth.signOut")}
      </button>
    </div>
  );
}
