import { describe, expect, it } from "vitest";

import { formatDuration, formatList, formatRelativeTime, formatWindow } from "./format";

const NOW = Date.parse("2026-11-10T12:00:00Z");

describe("formatRelativeTime", () => {
  it("should return minutes in French when the date is 5 minutes ago", () => {
    expect(formatRelativeTime("2026-11-10T11:55:00Z", NOW, "fr")).toBe("il y a 5 minutes");
  });

  it("should return hours in English when the date is 3 hours ago", () => {
    expect(formatRelativeTime("2026-11-10T09:00:00Z", NOW, "en")).toBe("3 hours ago");
  });

  it("should return days when the date is in the future", () => {
    expect(formatRelativeTime("2026-11-12T12:00:00Z", NOW, "en")).toBe("in 2 days");
  });

  it("should use the natural wording when the date is now", () => {
    expect(formatRelativeTime("2026-11-10T12:00:00Z", NOW, "fr")).toBe("maintenant");
  });

  it("should return null when the date is invalid", () => {
    expect(formatRelativeTime("not a date", NOW, "fr")).toBeNull();
  });
});

describe("formatWindow", () => {
  it("should return days when the window is a whole number of days", () => {
    expect(formatWindow(604_800, "en")).toBe("7 days");
  });

  it("should return hours when the window is not a whole number of days", () => {
    expect(formatWindow(7_200, "en")).toBe("2 hours");
  });

  it("should return seconds when the window is not a whole number of minutes", () => {
    expect(formatWindow(90, "en")).toBe("90 seconds");
  });
});

describe("formatDuration", () => {
  it("should return milliseconds below one second", () => {
    expect(formatDuration(420, "en")).toBe("420 ms");
  });

  it("should return seconds from one second", () => {
    expect(formatDuration(1500, "en")).toBe("1.5 sec");
  });
});

describe("formatList", () => {
  it("should join with the English conjunction", () => {
    expect(formatList(["Excel", "Access"], "en")).toBe("Excel and Access");
  });

  it("should join with the French conjunction", () => {
    expect(formatList(["Excel", "Access", "WhatsApp"], "fr")).toBe("Excel, Access et WhatsApp");
  });
});
