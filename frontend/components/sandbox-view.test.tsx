// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "./locale-provider";
import { SandboxView } from "./sandbox-view";

// Mock only the network boundary
vi.mock("../lib/services/normalize-service", () => ({ normalizeText: vi.fn() }));

import { normalizeText } from "../lib/services/normalize-service";

const FORMS = { text: "ciment 50 kg", norm: "ciment 50 kg", canonical: "ciment 50 kg", tokens: ["ciment", "50", "kg"], numbers: ["50"] };

function renderView() {
  return render(
    <LocaleProvider>
      <SandboxView />
    </LocaleProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("SandboxView", () => {
  it("should show the unavailable state when the endpoint answers 404", async () => {
    vi.mocked(normalizeText).mockResolvedValue({
      ok: false,
      error: { kind: "http", status: 404, code: undefined, retryAfterSeconds: undefined, fallbackRules: [] },
    });
    renderView();

    await userEvent.click(screen.getByRole("button", { name: /4 écritures du ciment/ }));

    expect(await screen.findByText("Bac à sable indisponible")).toBeTruthy();
  });

  it("should compare the first ciment variant with the three others when the example is chosen", async () => {
    vi.mocked(normalizeText).mockResolvedValue({ ok: true, data: { ...FORMS, comparisons: [] } });
    renderView();

    await userEvent.click(screen.getByRole("button", { name: /4 écritures du ciment/ }));

    expect(vi.mocked(normalizeText)).toHaveBeenCalledWith("ciment 50 kg", ["Ciment50kg", "cimént 50kg", "ciment (50kg)"]);
  });

  it("should show the score and the verdict of each comparison when the API answers", async () => {
    vi.mocked(normalizeText).mockResolvedValue({
      ok: true,
      data: {
        ...FORMS,
        comparisons: [{ ...FORMS, text: "Ciment50kg", score: 1, matched: true, method: "exact" }],
      },
    });
    renderView();

    await userEvent.click(screen.getByRole("button", { name: /4 écritures du ciment/ }));

    expect(await screen.findByText("100 %")).toBeTruthy();
    expect(screen.getByText("Correspond")).toBeTruthy();
  });

  it("should ask for a text when the input is empty", async () => {
    renderView();

    await userEvent.click(screen.getByRole("button", { name: "Analyser" }));

    expect(screen.getByText("Saisissez au moins un texte.")).toBeTruthy();
    expect(vi.mocked(normalizeText)).not.toHaveBeenCalled();
  });
});
