"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { MessageKey } from "../lib/i18n";
import { useI18n } from "./locale-provider";
import { LocaleSwitcher, ThemeToggle } from "./preferences-bar";
import { RequireAuth } from "./require-auth";
import { UserBar } from "./user-bar";

interface NavItem {
  href: string;
  label: MessageKey;
}

const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "nav.dashboard" },
  { href: "/rules", label: "nav.rules" },
  { href: "/correlations", label: "nav.correlations" },
  { href: "/sandbox", label: "nav.sandbox" },
];

export const MAIN_ID = "main";

function isCurrent(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Language and theme switches, for pages without the navigation (login). */
export function PreferencesRow() {
  return (
    <div className="toolbar">
      <LocaleSwitcher />
      <ThemeToggle />
    </div>
  );
}

function Shell({ children }: Readonly<{ children: React.ReactNode }>) {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <div className="page">
      <a className="skip-link" href={`#${MAIN_ID}`}>
        {t("a11y.skip")}
      </a>
      <header className="shell-header">
        <div className="shell-bar">
          <p className="brand font-display">{t("home.title")}</p>
          <div className="toolbar">
            <LocaleSwitcher />
            <ThemeToggle />
            <UserBar />
          </div>
        </div>
        <nav aria-label={t("nav.label")} className="nav">
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => {
              const current = isCurrent(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link href={item.href} className="nav-link" aria-current={current ? "page" : undefined}>
                    {t(item.label)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      <main id={MAIN_ID} className="page-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

/** Signed-in pages: authentication guard around the navigation shell. */
export function AppPage({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <RequireAuth>
      <Shell>{children}</Shell>
    </RequireAuth>
  );
}
