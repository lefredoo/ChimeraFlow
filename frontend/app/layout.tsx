import type { Metadata } from "next";
import "./globals.css";
import "./components.css";
import { AuthProvider } from "../components/auth-provider";
import { LocaleProvider } from "../components/locale-provider";
import { ThemeProvider } from "../components/theme-provider";
import { DEFAULT_LOCALE, t } from "../lib/i18n";

export const metadata: Metadata = {
  title: t("meta.title"),
  description: t("meta.description"),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang={DEFAULT_LOCALE}>
      <body className="font-sans">
        <LocaleProvider>
          <ThemeProvider>
            <AuthProvider>{children}</AuthProvider>
          </ThemeProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
