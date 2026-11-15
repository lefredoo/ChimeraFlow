// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { Correlation } from "../lib/api-types";
import { CorrelationCard } from "./correlation-card";
import { LocaleProvider } from "./locale-provider";

const NOW = Date.parse("2026-11-10T12:00:00Z");

const BASE: Correlation = {
  id: 1,
  rule_id: "r_low_stock",
  detected_at: "2026-11-10T11:55:00Z",
  severity: "warning",
  message: "Stock bas : ciment 50 kg",
  provenance: [
    { source: "whatsapp", source_ref: "chat.txt#L412", record_id: "wa-0412" },
    { source: "access", source_ref: "STOCK_ZOBO.mdb#Articles/16", record_id: "ac-16" },
  ],
};

function renderCard(correlation: Correlation) {
  return render(
    <LocaleProvider>
      <CorrelationCard correlation={correlation} now={NOW} />
    </LocaleProvider>,
  );
}

afterEach(cleanup);

describe("CorrelationCard", () => {
  it("should render a message containing HTML as text, not as markup", () => {
    const hostile = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const { container } = renderCard({ ...BASE, message: hostile });

    expect(screen.getByText(hostile)).toBeTruthy();
    expect(container.querySelector("img, script")).toBeNull();
  });

  it("should show one badge per contributing source", () => {
    renderCard(BASE);

    expect(screen.getByText("Access")).toBeTruthy();
    expect(screen.getByText("WhatsApp")).toBeTruthy();
  });

  it("should not offer the explanation when the correlation has none", () => {
    renderCard(BASE);

    expect(screen.queryByRole("button", { name: "Pourquoi ça correspond" })).toBeNull();
  });

  it("should show an unknown explanation shape as text after a click", async () => {
    renderCard({ ...BASE, explanation: { matched_on: "<b>ciment 50 kg</b>", score: 1 } });

    await userEvent.click(screen.getByRole("button", { name: "Pourquoi ça correspond" }));

    expect(screen.getByText("<b>ciment 50 kg</b>")).toBeTruthy();
  });

  it("should describe the engine explanation in words after a click", async () => {
    renderCard({
      ...BASE,
      explanation: {
        trigger: {
          source: "whatsapp",
          record_id: "wa-0412",
          entity: { raw: "ciment 50kg", norm: "ciment 50 kg" },
          where: [],
        },
        joins: [
          {
            source: "access",
            record_id: "ac-16",
            candidate: { raw: "Ciment 50 kg", norm: "ciment 50 kg" },
            score: 1,
            method: "exact",
            where: [{ field: "qty_stock", op: "lt", expected: 10, actual: 5, passed: true }],
          },
        ],
      },
    });

    await userEvent.click(screen.getByRole("button", { name: "Pourquoi ça correspond" }));

    expect(screen.getByText(/Même nom après normalisation/)).toBeTruthy();
    expect(screen.getByText(/qty_stock < 10 ; valeur trouvée : 5/)).toBeTruthy();
  });

  it("should list the provenance of each record in the drawer", async () => {
    renderCard(BASE);

    await userEvent.click(screen.getByRole("button", { name: /Provenance/ }));

    expect(screen.getByText("chat.txt#L412")).toBeTruthy();
    expect(screen.getByText("ac-16")).toBeTruthy();
  });
});
