import { describe, expect, it } from "vitest";

import en from "../messages/en.json";
import fr from "../messages/fr.json";
import { isLocale, tp } from "./i18n";

describe("tp", () => {
  it("should use the singular form in French when the count is 0", () => {
    expect(tp("rules.count", 0, undefined, "fr")).toBe("0 règle");
  });

  it("should use the plural form in French when the count is 2", () => {
    expect(tp("rules.count", 2, undefined, "fr")).toBe("2 règles");
  });

  it("should use the plural form in English when the count is 0", () => {
    expect(tp("rules.count", 0, undefined, "en")).toBe("0 rules");
  });

  it("should format the count with the thousands separator of the locale", () => {
    expect(tp("sources.records", 1500, undefined, "en")).toBe("1,500 records");
  });

  it("should fill extra placeholders", () => {
    expect(tp("dashboard.degraded.body", 1, { sources: "Access" }, "en")).toContain("Access is unavailable");
  });
});

describe("plural messages", () => {
  it.each([
    ["fr", fr],
    ["en", en],
  ] as const)("should define the one and other forms of every plural message in %s", (_name, catalog) => {
    const keys = Object.keys(catalog);
    const bases = keys.filter((key) => key.endsWith(".other")).map((key) => key.slice(0, -".other".length));
    const missing = bases.filter((base) => !keys.includes(`${base}.one`));
    expect(missing).toEqual([]);
  });

  it("should keep the same placeholders in French and English for every key", () => {
    const placeholders = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();
    const frCatalog: Record<string, string> = fr;
    const mismatched = Object.entries(en as Record<string, string>)
      .filter(([key, text]) => JSON.stringify(placeholders(text)) !== JSON.stringify(placeholders(frCatalog[key])))
      .map(([key]) => key);
    expect(mismatched).toEqual([]);
  });
});

describe("isLocale", () => {
  it("should accept fr and en only", () => {
    expect([isLocale("fr"), isLocale("en"), isLocale("de"), isLocale(null)]).toEqual([true, true, false, false]);
  });
});
