import { describe, expect, it } from "vitest";

import { optionalEnv, requireEnv, requireEnvUrl } from "./env";

describe("requireEnv", () => {
  it("should throw naming the variable when it is undefined", () => {
    expect(() => requireEnv("API_URL", "API service URL", undefined)).toThrow(/API_URL.*API service URL/);
  });

  it("should throw when the value is blank", () => {
    expect(() => requireEnv("API_URL", "API service URL", "  ")).toThrow(/API_URL/);
  });

  it("should return the value when it is set", () => {
    expect(requireEnv("API_URL", "API service URL", "abc")).toBe("abc");
  });
});

describe("requireEnvUrl", () => {
  it("should remove trailing slashes when the URL is valid", () => {
    expect(requireEnvUrl("API_URL", "API service URL", "https://api.example.com//")).toBe(
      "https://api.example.com",
    );
  });

  it("should throw when the value is not a URL", () => {
    expect(() => requireEnvUrl("API_URL", "API service URL", "not a url")).toThrow(/valid URL/);
  });

  it("should throw when the protocol is not http or https", () => {
    expect(() => requireEnvUrl("API_URL", "API service URL", "ftp://example.com")).toThrow(/http or https/);
  });
});

describe("optionalEnv", () => {
  it("should return undefined when the value is empty", () => {
    expect(optionalEnv("")).toBeUndefined();
  });

  it("should return the value when it is set", () => {
    expect(optionalEnv("x")).toBe("x");
  });
});
