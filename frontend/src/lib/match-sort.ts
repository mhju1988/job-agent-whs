import type { Match } from "./types";

export type MatchSort = "high_low" | "low_high" | "recent";

/**
 * Sort matches for display. Pure — returns a new array.
 *
 * NOTE: `recent` sorts by `created_at` (when the match was SCORED), not by
 * `jobs.scraped_at` (when the job was POSTED). This is intentional — do not
 * "fix" it to scraped_at; users expect their newest scoring activity first.
 */
export function sortMatches(matches: Match[], mode: MatchSort): Match[] {
  const arr = [...matches];
  if (mode === "low_high") {
    // null scores sink to the bottom under ascending sort (treat null as +inf).
    const lowKey = (x: Match) => x.score ?? Number.POSITIVE_INFINITY;
    return arr.sort((a, b) => lowKey(a) - lowKey(b));
  }
  if (mode === "recent") {
    // null/empty created_at sinks to the bottom (empty string sorts last desc).
    return arr.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  }
  // high_low (default): null scores sink to the bottom (treat null as -inf).
  const highKey = (x: Match) => x.score ?? Number.NEGATIVE_INFINITY;
  return arr.sort((a, b) => highKey(b) - highKey(a));
}
