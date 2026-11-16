import type { SourceInfo } from "./api-types";

/** Sources that are not fully healthy (status degraded or error). */
export function unhealthySources(sources: readonly SourceInfo[]): SourceInfo[] {
  return sources.filter((source) => source.status !== "ok");
}

/** Count of sources that answered `ok`. */
export function healthyCount(sources: readonly SourceInfo[]): number {
  return sources.filter((source) => source.status === "ok").length;
}
