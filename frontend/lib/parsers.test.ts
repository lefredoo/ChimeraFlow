import { describe, expect, it } from "vitest";

import {
  isCorrelation,
  isRule,
  isRuleDraft,
  parseExecutionSummary,
  parseNormalizeResult,
  parseRecordCounts,
  parseSources,
} from "./parsers";

const DRAFT = {
  id: "r_nl_0123456789ab",
  natural_language: "Quand un client demande du ciment, alerte-moi si le stock est bas.",
  trigger: { source: "whatsapp", entity: "product" },
  joins: [{ source: "access", table: "Articles", on: { entity: "product", field: "designation" }, where: [] }],
  window_seconds: 604_800,
  emit: { severity: "warning", template: "Stock bas : {product}" },
};

const CORRELATION = {
  id: 7,
  rule_id: "r_low_stock",
  detected_at: "2026-11-10T10:00:00+01:00",
  severity: "warning",
  message: "Stock bas",
  provenance: [{ source: "access", source_ref: "STOCK_ZOBO.mdb#Articles/16", record_id: "ac-16" }],
};

describe("isRuleDraft", () => {
  it("should accept a valid draft", () => {
    expect(isRuleDraft(DRAFT)).toBe(true);
  });

  it("should accept a draft with trigger-side conditions", () => {
    const withWhere = { ...DRAFT, trigger: { ...DRAFT.trigger, where: [{ field: "status", op: "eq", value: "ok" }] } };
    expect(isRuleDraft(withWhere)).toBe(true);
  });

  it("should reject a draft with an unknown source", () => {
    expect(isRuleDraft({ ...DRAFT, trigger: { source: "sms", entity: "product" } })).toBe(false);
  });

  it("should reject a join with an unknown operator", () => {
    const bad = { ...DRAFT, joins: [{ ...DRAFT.joins[0], where: [{ field: "q", op: "regex", value: 1 }] }] };
    expect(isRuleDraft(bad)).toBe(false);
  });

  it("should reject a non-object", () => {
    expect(isRuleDraft("rule")).toBe(false);
  });
});

describe("isRule", () => {
  it("should require the stored fields", () => {
    expect(isRule(DRAFT)).toBe(false);
  });

  it("should accept a stored rule", () => {
    const stored = { ...DRAFT, version: 1, status: "active", created_at: "2026-11-10T09:00:00", updated_at: "2026-11-10T09:00:00" };
    expect(isRule(stored)).toBe(true);
  });
});

describe("isCorrelation", () => {
  it("should accept a correlation without explanation", () => {
    expect(isCorrelation(CORRELATION)).toBe(true);
  });

  it("should accept a correlation with a structured explanation", () => {
    expect(isCorrelation({ ...CORRELATION, explanation: { score: 0.93, matched: ["ciment", "50"] } })).toBe(true);
  });

  it("should reject a correlation with an unknown severity", () => {
    expect(isCorrelation({ ...CORRELATION, severity: "critical" })).toBe(false);
  });

  it("should reject a correlation with malformed provenance", () => {
    expect(isCorrelation({ ...CORRELATION, provenance: [{ source: "access" }] })).toBe(false);
  });
});

describe("parseSources", () => {
  it("should read the health of each source", () => {
    const body = { sources: [{ name: "excel", status: "ok", message: "", last_fetch: "2026-11-10T10:00:00" }] };
    expect(parseSources(body)).toEqual([{ name: "excel", status: "ok", message: "", lastFetch: "2026-11-10T10:00:00" }]);
  });

  it("should never read an unknown status as healthy", () => {
    expect(parseSources({ sources: [{ name: "momo", status: "weird" }] })?.[0].status).toBe("error");
  });

  it("should reject an unknown source name", () => {
    expect(parseSources({ sources: [{ name: "sms", status: "ok" }] })).toBeUndefined();
  });
});

describe("parseRecordCounts", () => {
  it("should count the records of each source", () => {
    const body = { records: [{ source: "excel" }, { source: "excel" }, { source: "momo" }] };
    expect(parseRecordCounts(body)).toEqual({ excel: 2, momo: 1 });
  });
});

describe("parseExecutionSummary", () => {
  it("should read a successful run", () => {
    const body = { status: "success", rules_executed: 4, rules_failed: 1, correlations_found: 9, records_scanned: 120, duration_ms: 350 };
    expect(parseExecutionSummary(body)).toEqual(body);
  });

  it("should read the no_rules answer", () => {
    const body = { status: "no_rules", message: "x", rules_executed: 0, rules_failed: 0, correlations_found: 0 };
    expect(parseExecutionSummary(body)?.status).toBe("no_rules");
  });

  it("should reject a success answer without duration", () => {
    expect(parseExecutionSummary({ status: "success", rules_executed: 1, rules_failed: 0, correlations_found: 0 })).toBeUndefined();
  });
});

describe("parseNormalizeResult", () => {
  const forms = { text: "Ciment50kg", norm: "ciment 50 kg", canonical: "ciment 50 kg", tokens: ["ciment", "50", "kg"], numbers: ["50"] };

  it("should read the reference text and its comparisons", () => {
    const comparison = { ...forms, text: "ciment 50 kg", score: 1, matched: true, method: "exact" };
    expect(parseNormalizeResult({ ...forms, comparisons: [comparison] })).toEqual({ ...forms, comparisons: [comparison] });
  });

  it("should read a comparison without method as null", () => {
    const comparison = { ...forms, score: 0.2, matched: false, method: null };
    expect(parseNormalizeResult({ ...forms, comparisons: [comparison] })?.comparisons[0].method).toBeNull();
  });

  it("should display numbers sent as numbers", () => {
    expect(parseNormalizeResult({ ...forms, numbers: [50], comparisons: [] })?.numbers).toEqual(["50"]);
  });

  it("should reject an answer without comparisons", () => {
    expect(parseNormalizeResult(forms)).toBeUndefined();
  });

  it("should reject a comparison without score", () => {
    expect(parseNormalizeResult({ ...forms, comparisons: [{ ...forms, matched: true }] })).toBeUndefined();
  });
});
