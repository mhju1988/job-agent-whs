import type { Match } from "./types";

/** A skill the user is missing, and how many of their matches flagged it. */
export interface GapCount {
  skill: string;
  count: number;
}

/**
 * Aggregates per-match `gaps` into the most common missing skills. Merges
 * case-insensitively (keeping the first-seen display casing), sorts by count
 * descending then skill ascending, and returns the top `limit`.
 */
export function topGaps(matches: Match[], limit: number): GapCount[] {
  const byKey = new Map<string, GapCount>();
  for (const m of matches) {
    for (const raw of m.gaps ?? []) {
      const skill = raw.trim();
      if (!skill) continue;
      const key = skill.toLowerCase();
      const existing = byKey.get(key);
      if (existing) existing.count += 1;
      else byKey.set(key, { skill, count: 1 });
    }
  }
  return Array.from(byKey.values())
    .sort((a, b) => b.count - a.count || a.skill.localeCompare(b.skill))
    .slice(0, limit);
}
