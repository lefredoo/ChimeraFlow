import { describe, expect, it } from "vitest";

import en from "../messages/en.json";
import fr from "../messages/fr.json";
import { t } from "./i18n";

describe("t", () => {
  it("should return the French message when no locale is given", () => {
    expect(t("status.heading")).toBe(fr["status.heading"]);
  });

  it("should return the English message when the locale is en", () => {
    expect(t("status.heading", undefined, "en")).toBe(en["status.heading"]);
  });
});

describe("messages", () => {
  it("should have the same keys in French and English", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
  });
});
