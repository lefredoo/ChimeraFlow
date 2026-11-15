"use client";

import { t } from "../lib/i18n";
import { useAuth } from "./auth-provider";

/** Signed-in account and sign-out button. Renders nothing when nobody is signed in. */
export function UserBar() {
  const { state, signOut } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  return (
    <div className="user-bar">
      <span className="text-muted">{t("auth.signedInAs", { email: state.email })}</span>
      <button type="button" className="button button-secondary" onClick={signOut}>
        {t("auth.signOut")}
      </button>
    </div>
  );
}
