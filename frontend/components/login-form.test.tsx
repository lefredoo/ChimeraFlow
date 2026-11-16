// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearSession } from "../lib/auth/token-storage";
import { AuthProvider } from "./auth-provider";
import { LocaleProvider } from "./locale-provider";
import { LoginForm } from "./login-form";

const DEMO_EMAIL = "demo@example.test";
const DEMO_PASSWORD = "demo-password-for-tests";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));

// Mock only the boundaries: router, public demo configuration and the network
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("../lib/config", () => ({ API_URL: "http://api.test" }));
vi.mock("../lib/demo-credentials", () => ({
  DEMO_LOGIN_EMAIL: "demo@example.test",
  DEMO_LOGIN_PASSWORD: "demo-password-for-tests",
}));
vi.mock("../lib/services/auth-service", () => ({ login: vi.fn(), fetchCurrentUser: vi.fn() }));

import { login } from "../lib/services/auth-service";

const SESSION = { token: "token", email: DEMO_EMAIL, expiresAt: Date.now() + 3_600_000 };

function renderForm() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <LoginForm />
      </AuthProvider>
    </LocaleProvider>,
  );
}

beforeEach(() => {
  clearSession();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("LoginForm", () => {
  it("should keep the credentials out of the page when it first renders", () => {
    renderForm();

    expect(screen.queryByText(DEMO_PASSWORD)).toBeNull();
    expect(screen.getByRole("button", { name: "Voir les identifiants" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("should show the credentials and set aria-expanded when the reveal button is pressed", async () => {
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Voir les identifiants" }));

    expect(screen.getByText(DEMO_EMAIL)).toBeTruthy();
    expect(screen.getByText(DEMO_PASSWORD)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Masquer les identifiants" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("should hide the credentials again when the reveal button is pressed twice", async () => {
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Voir les identifiants" }));
    await userEvent.click(screen.getByRole("button", { name: "Masquer les identifiants" }));

    expect(screen.queryByText(DEMO_PASSWORD)).toBeNull();
    expect(screen.getByRole("button", { name: "Voir les identifiants" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("should sign in with the demo account and go home when the demo button is pressed", async () => {
    vi.mocked(login).mockResolvedValue({ state: "success", session: SESSION });
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Entrer dans la démo" }));

    expect(vi.mocked(login)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(login)).toHaveBeenCalledWith(DEMO_EMAIL, DEMO_PASSWORD);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("should announce the error in the alert region when the credentials are refused", async () => {
    vi.mocked(login).mockResolvedValue({ state: "invalid_credentials" });
    renderForm();

    await userEvent.type(screen.getByLabelText("Adresse email"), "someone@example.test");
    await userEvent.type(screen.getByLabelText("Mot de passe", { selector: "input" }), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    const alert = await screen.findByText("Email ou mot de passe incorrect.");
    expect(alert.getAttribute("role")).toBe("alert");
    expect(replace).not.toHaveBeenCalled();
  });

  it("should link the error to both fields when the credentials are refused", async () => {
    vi.mocked(login).mockResolvedValue({ state: "invalid_credentials" });
    renderForm();

    await userEvent.type(screen.getByLabelText("Adresse email"), "someone@example.test");
    await userEvent.type(screen.getByLabelText("Mot de passe", { selector: "input" }), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    const alert = await screen.findByRole("alert");
    const email = screen.getByLabelText("Adresse email");
    expect(email.getAttribute("aria-invalid")).toBe("true");
    expect(email.getAttribute("aria-describedby")).toBe(alert.id);
  });

  it("should announce the delay when the login is rate limited", async () => {
    vi.mocked(login).mockResolvedValue({ state: "rate_limited", retryAfterSeconds: 30 });
    renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Entrer dans la démo" }));

    expect((await screen.findByRole("alert")).textContent).toBe("Trop de tentatives. Réessayez dans 30 s.");
  });
});
