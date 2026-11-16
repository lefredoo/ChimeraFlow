"use client";

import type { SourceName } from "../lib/api-types";
import { SourceBadge } from "./badges";
import { useI18n } from "./locale-provider";

export interface SeamItem {
  source: SourceName;
  /** `broken` draws the thread to this source as cut: the source is down. */
  state: "joined" | "broken";
}

/**
 * The sources of a correlation stitched together by a dashed thread: the
 * product's signature (several records, one thing). A broken thread marks a
 * source that is unavailable. Meaning is also in the text of each badge and in
 * the list label, never in the thread alone.
 */
export function Seam({ items }: Readonly<{ items: readonly SeamItem[] }>) {
  const { t } = useI18n();
  return (
    <ul className="seam" aria-label={t("seam.label")}>
      {items.map((item, index) => (
        <li key={item.source} className="seam-item">
          {index > 0 && <span className="seam-thread" data-state={item.state} aria-hidden="true" />}
          <SourceBadge source={item.source} />
        </li>
      ))}
    </ul>
  );
}
