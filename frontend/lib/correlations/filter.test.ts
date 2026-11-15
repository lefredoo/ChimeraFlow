import { describe, expect, it } from "vitest";

import type { Correlation } from "../api-types";
import { NO_FILTERS, contributingSources, countBySeverity, filterCorrelations, ruleIdsOf } from "./filter";

function correlation(id: number, ruleId: string, severity: Correlation["severity"]): Correlation {
  return { id, rule_id: ruleId, detected_at: "2026-11-10T10:00:00Z", severity, message: `m${id}`, provenance: [] };
}

const SAMPLE = [correlation(1, "r_a", "info"), correlation(2, "r_b", "warning"), correlation(3, "r_a", "warning")];

describe("filterCorrelations", () => {
  it("should return everything when no filter is set", () => {
    expect(filterCorrelations(SAMPLE, NO_FILTERS)).toEqual(SAMPLE);
  });

  it("should keep only the requested severity", () => {
    expect(filterCorrelations(SAMPLE, { severity: "warning", ruleId: "" }).map((c) => c.id)).toEqual([2, 3]);
  });

  it("should keep only the requested rule", () => {
    expect(filterCorrelations(SAMPLE, { severity: "", ruleId: "r_a" }).map((c) => c.id)).toEqual([1, 3]);
  });

  it("should combine both filters", () => {
    expect(filterCorrelations(SAMPLE, { severity: "warning", ruleId: "r_a" }).map((c) => c.id)).toEqual([3]);
  });

  it("should return nothing when no correlation matches", () => {
    expect(filterCorrelations(SAMPLE, { severity: "error", ruleId: "" })).toEqual([]);
  });
});

describe("ruleIdsOf", () => {
  it("should return distinct sorted rule ids", () => {
    expect(ruleIdsOf([...SAMPLE].reverse())).toEqual(["r_a", "r_b"]);
  });
});

describe("contributingSources", () => {
  it("should return distinct sources in the canonical order", () => {
    const provenance = [
      { source: "whatsapp", source_ref: "chat.txt#L4", record_id: "wa-4" },
      { source: "excel", source_ref: "t.xlsx#R3", record_id: "xl-3" },
      { source: "whatsapp", source_ref: "chat.txt#L9", record_id: "wa-9" },
    ] as const;
    expect(contributingSources(provenance)).toEqual(["excel", "whatsapp"]);
  });
});

describe("countBySeverity", () => {
  it("should count each severity", () => {
    expect(countBySeverity(SAMPLE)).toEqual({ info: 1, warning: 2, error: 0 });
  });
});
