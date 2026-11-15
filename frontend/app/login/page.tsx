import type { Metadata } from "next";

import { LoginView } from "../../components/login-view";
import { t } from "../../lib/i18n";

export const metadata: Metadata = {
  title: t("login.meta.title"),
};

export default function LoginPage() {
  return <LoginView />;
}
