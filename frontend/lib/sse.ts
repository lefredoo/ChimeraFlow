export interface SseEvent {
  /** Event name; "message" when the stream gives none. */
  event: string;
  data: string;
}

/**
 * Split a Server-Sent Events text stream into complete events.
 *
 * The browser's `EventSource` cannot send an `Authorization` header, so the
 * stream is read with `fetch` and parsed here.
 *
 * @param buffer Text left over from the previous call.
 * @param chunk Newly received text.
 * @returns Complete events and the incomplete tail to pass to the next call.
 */
export function parseSseChunk(buffer: string, chunk: string): { events: SseEvent[]; rest: string } {
  const text = (buffer + chunk).replace(/\r\n?/g, "\n");
  const blocks = text.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SseEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line === "" || line.startsWith(":")) {
        continue;
      }
      const separator = line.indexOf(":");
      const field = separator === -1 ? line : line.slice(0, separator);
      const value = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
      if (field === "event") {
        event = value;
      } else if (field === "data") {
        data.push(value);
      }
    }
    // A block of comments only (keep-alive) carries no event
    if (data.length > 0) {
      events.push({ event, data: data.join("\n") });
    }
  }
  return { events, rest };
}
