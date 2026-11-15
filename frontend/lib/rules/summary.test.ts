import { describe, expect, it } from "vitest";

import type { RuleDraft } from "../api-types";
import { prettyRuleJson, summarizeRule } from "./summary";

const LOW_STOCK: RuleDraft = {
  id: "r_low_stock",
  natural_language: "Alerter quand le stock est bas.",
  trigger: { source: "whatsapp", entity: "product" },
  joins: [
    {
      source: "access",
      table: "Articles",
      on: { entity: "product", field: "designation" },
      where: [{ field: "qty_stock", op: "lt", value: 10 }],
    },
    { source: "excel", sheet: "Tarifs", on: { entity: "product", field: "Produit" } },
  ],
  window_seconds: 604_800,
  emit: { severity: "warning", template: "Stock bas : {product}" },
};

describe("summarizeRule", () => {
  it("should describe the trigger", () => {
    expect(summarizeRule(LOW_STOCK).trigger).toEqual({ source: "whatsapp", entity: "product", conditions: [] });
  });

  it("should name the Access table and the condition of a join", () => {
    expect(summarizeRule(LOW_STOCK).joins[0]).toEqual({
      source: "access",
      location: { kind: "table", name: "Articles" },
      field: "designation",
      conditions: [{ field: "qty_stock", op: "lt", value: "10", ref: null, tolerancePct: null }],
    });
  });

  it("should name the Excel sheet of a join without conditions", () => {
    expect(summarizeRule(LOW_STOCK).joins[1]).toMatchObject({ location: { kind: "sheet", name: "Tarifs" }, conditions: [] });
  });

  it("should keep the window and the severity", () => {
    expect(summarizeRule(LOW_STOCK)).toMatchObject({ windowSeconds: 604_800, severity: "warning" });
  });

  it("should include trigger-side conditions when the rule has them", () => {
    const rule: RuleDraft = {
      ...LOW_STOCK,
      trigger: { source: "momo", entity: "product", where: [{ field: "status", op: "in", value: ["ok", "done"] }] },
    };
    expect(summarizeRule(rule).trigger.conditions).toEqual([
      { field: "status", op: "in", value: "ok, done", ref: null, tolerancePct: null },
    ]);
  });

  it("should describe a condition that compares with another record and a tolerance", () => {
    const rule: RuleDraft = {
      ...LOW_STOCK,
      joins: [
        {
          source: "excel",
          sheet: "Tarifs",
          on: { entity: "product", field: "Produit" },
          where: [{ field: "Prix_Unitaire", op: "gt", ref: "access.prix_achat", tolerance_pct: 10 }],
        },
      ],
    };
    expect(summarizeRule(rule).joins[0].conditions).toEqual([
      { field: "Prix_Unitaire", op: "gt", value: "", ref: "access.prix_achat", tolerancePct: 10 },
    ]);
  });

  it("should describe a join without location", () => {
    const rule: RuleDraft = {
      ...LOW_STOCK,
      joins: [{ source: "whatsapp", on: { entity: "product", field: "text" } }],
    };
    expect(summarizeRule(rule).joins[0].location).toBeNull();
  });
});

describe("prettyRuleJson", () => {
  it("should indent with two spaces and keep unknown fields", () => {
    expect(prettyRuleJson({ id: "r", future: { a: 1 } })).toBe('{\n  "id": "r",\n  "future": {\n    "a": 1\n  }\n}');
  });
});
