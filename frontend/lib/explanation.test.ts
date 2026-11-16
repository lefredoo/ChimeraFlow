import { describe, expect, it } from "vitest";

import { displayValue, parseExplanation } from "./explanation";

const ENGINE_EXPLANATION = {
  trigger: {
    source: "whatsapp",
    record_id: "wa-0412",
    source_ref: "chat.txt#L412",
    entity: { raw: "ciment 50kg", norm: "ciment 50 kg" },
    where: [],
  },
  joins: [
    {
      source: "access",
      record_id: "ac-16",
      source_ref: "STOCK_ZOBO.mdb#Articles/16",
      on: { entity: "product", field: "designation" },
      candidate: { raw: "Ciment 50 kg", norm: "ciment 50 kg" },
      score: 1,
      method: "exact",
      candidates: 1,
      where: [{ field: "qty_stock", op: "lt", expected: 10, actual: 5, passed: true }],
    },
    {
      source: "excel",
      record_id: "xl-3",
      source_ref: "tarifs.xlsx#R3",
      on: { entity: "product", field: "Produit" },
      candidate: { raw: "Ciment 50 kg", norm: "ciment 50 kg" },
      score: 0.9,
      method: "token",
      candidates: 2,
      where: [{ field: "Prix_Unitaire", op: "gt", ref: "access.prix_achat", tolerance_pct: 10, expected: 45000, actual: 60000, gap_pct: 33.3, passed: true }],
    },
  ],
};

describe("parseExplanation", () => {
  it("should read the trigger entity", () => {
    expect(parseExplanation(ENGINE_EXPLANATION)?.trigger).toMatchObject({
      source: "whatsapp",
      recordId: "wa-0412",
      entity: { raw: "ciment 50kg", norm: "ciment 50 kg" },
    });
  });

  it("should read the method, score and condition outcomes of each join", () => {
    const joins = parseExplanation(ENGINE_EXPLANATION)?.joins;
    expect(joins?.[0]).toMatchObject({
      source: "access",
      method: "exact",
      score: 1,
      where: [{ field: "qty_stock", op: "lt", expected: 10, actual: 5, passed: true, ref: null }],
    });
  });

  it("should read the reference, tolerance and gap of a relative condition", () => {
    expect(parseExplanation(ENGINE_EXPLANATION)?.joins[1].where[0]).toMatchObject({
      ref: "access.prix_achat",
      tolerancePct: 10,
      gapPct: 33.3,
    });
  });

  it("should return null for a shape the engine does not produce", () => {
    expect(parseExplanation({ reason: "same product" })).toBeNull();
  });

  it("should return null when a join has an unknown source", () => {
    const broken = { ...ENGINE_EXPLANATION, joins: [{ ...ENGINE_EXPLANATION.joins[0], source: "sms" }] };
    expect(parseExplanation(broken)).toBeNull();
  });

  it("should return null for a string", () => {
    expect(parseExplanation("because")).toBeNull();
  });
});

describe("displayValue", () => {
  it("should join list items", () => {
    expect(displayValue(["a", 2])).toBe("a, 2");
  });

  it("should return an empty string for null", () => {
    expect(displayValue(null)).toBe("");
  });
});
