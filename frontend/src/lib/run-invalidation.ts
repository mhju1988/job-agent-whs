import type { RunKind } from "./types";

/**
 * Query keys to invalidate after a completed agent run — replaces a blanket
 * `qc.invalidateQueries()` that refetched every query.
 *
 * Every kind includes `["runs"]`: each run writes an `agent_runs` row, so the
 * dashboard's "Recent activity" list must refresh. `writer` also touches
 * `["matches"]` because the matches query embeds `jobs(... applications(...))`,
 * so creating an application updates the ApplicationReadyBadge there.
 *
 * Exhaustive over RunKind (non-optional return) — a new run kind forces an
 * entry here at compile time.
 */
export function runInvalidationKeys(kind: RunKind): string[][] {
  switch (kind) {
    case "scout":
      return [["jobs"], ["runs"]];
    case "matcher":
      return [["matches"], ["runs"]];
    case "scout-matcher":
      return [["jobs"], ["matches"], ["runs"]];
    case "writer":
      return [["applications"], ["matches"], ["runs"]];
    case "rescore":
      return [["matches"], ["runs"]];
  }
}
