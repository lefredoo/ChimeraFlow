import { describe, expect, it } from "vitest";

import { validateComposerText } from "./composer";
import { CIMENT_VARIANTS, SANDBOX_MAX_COMPARISONS, formatScore, parseSandboxInput } from "./sandbox";

describe("parseSandboxInput", () => {
  it("should take the first line as reference and drop blank lines", () => {
    expect(parseSandboxInput("ciment 50 kg\n\n  Ciment50kg  \r\n")).toEqual({
      ok: true,
      text: "ciment 50 kg",
      compareWith: ["Ciment50kg"],
    });
  });

  it("should have no comparison when there is a single line", () => {
    expect(parseSandboxInput("ciment")).toEqual({ ok: true, text: "ciment", compareWith: [] });
  });

  it("should reject an empty input", () => {
    expect(parseSandboxInput("  \n ")).toEqual({ ok: false, reason: "empty" });
  });

  it("should reject more comparisons than the limit", () => {
    const lines = Array.from({ length: SANDBOX_MAX_COMPARISONS + 2 }, (_, index) => `texte ${index}`).join("\n");
    expect(parseSandboxInput(lines)).toEqual({ ok: false, reason: "too_many" });
  });

  it("should reject a line that is too long", () => {
    expect(parseSandboxInput("x".repeat(201))).toEqual({ ok: false, reason: "too_long" });
  });

  it("should compare the first ciment variant with the three others", () => {
    expect(parseSandboxInput(CIMENT_VARIANTS.join("\n"))).toEqual({
      ok: true,
      text: "ciment 50 kg",
      compareWith: ["Ciment50kg", "cimént 50kg", "ciment (50kg)"],
    });
  });
});

describe("formatScore", () => {
  it("should return a localized percentage", () => {
    expect(formatScore(0.857, "en")).toBe("86%");
  });
});

describe("validateComposerText", () => {
  it("should be too short below 20 characters after trimming", () => {
    expect(validateComposerText("   court   ")).toBe("too_short");
  });

  it("should be ok at exactly 20 characters", () => {
    expect(validateComposerText("a".repeat(20))).toBe("ok");
  });

  it("should be too long above 1000 characters", () => {
    expect(validateComposerText("a".repeat(1001))).toBe("too_long");
  });
});
