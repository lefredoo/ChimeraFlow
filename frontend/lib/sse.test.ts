import { describe, expect, it } from "vitest";

import { parseSseChunk } from "./sse";

describe("parseSseChunk", () => {
  it("should return one event when a block is complete", () => {
    expect(parseSseChunk("", "event: correlation\ndata: {\"id\":1}\n\n")).toEqual({
      events: [{ event: "correlation", data: '{"id":1}' }],
      rest: "",
    });
  });

  it("should name the event message when the stream gives no name", () => {
    expect(parseSseChunk("", "data: hello\n\n").events).toEqual([{ event: "message", data: "hello" }]);
  });

  it("should keep an incomplete block in rest", () => {
    expect(parseSseChunk("", "data: par")).toEqual({ events: [], rest: "data: par" });
  });

  it("should complete a block split across two chunks", () => {
    const first = parseSseChunk("", "data: par");
    expect(parseSseChunk(first.rest, "tial\n\n").events).toEqual([{ event: "message", data: "partial" }]);
  });

  it("should ignore keep-alive comments", () => {
    expect(parseSseChunk("", ": keep-alive\n\n").events).toEqual([]);
  });

  it("should join multi-line data with a newline", () => {
    expect(parseSseChunk("", "data: a\ndata: b\n\n").events).toEqual([{ event: "message", data: "a\nb" }]);
  });

  it("should accept CRLF line endings", () => {
    expect(parseSseChunk("", "data: x\r\n\r\n").events).toEqual([{ event: "message", data: "x" }]);
  });
});
