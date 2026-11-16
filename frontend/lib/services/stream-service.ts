import { parseSseChunk, type SseEvent } from "../sse";
import { apiFetch } from "./api-client";

export const CORRELATION_STREAM_PATH = "/api/v1/correlations/stream";

/**
 * - `unsupported`: the backend has no usable stream (404, other error, wrong content type)
 * - `closed`: the stream worked and then ended (network drop, server restart)
 * - `aborted`: the caller cancelled
 */
export type StreamOutcome = "unsupported" | "closed" | "aborted";

/**
 * Read the correlation event stream until it ends.
 *
 * @param onEvent Called for each event received.
 * @param onOpen Called once when the stream is established.
 * @param signal Cancels the stream.
 */
export async function readCorrelationStream(
  onEvent: (event: SseEvent) => void,
  onOpen: () => void,
  signal: AbortSignal,
): Promise<StreamOutcome> {
  let response: Response;
  try {
    response = await apiFetch(CORRELATION_STREAM_PATH, {
      headers: { Accept: "text/event-stream" },
      signal,
    });
  } catch {
    // Network failure: the stream may work next time, so it is not "unsupported"
    return signal.aborted ? "aborted" : "closed";
  }
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!response.ok || response.body === null || !contentType.includes("text/event-stream")) {
    return "unsupported";
  }
  onOpen();
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        return "closed";
      }
      const parsed = parseSseChunk(buffer, value);
      buffer = parsed.rest;
      parsed.events.forEach(onEvent);
    }
  } catch {
    return signal.aborted ? "aborted" : "closed";
  }
}
