/** Score banding for the Matches page: strong (70+), good (50–69), weak (<50). */

export type Band = "strong" | "good" | "weak";

export function scoreBand(score: number | null | undefined): Band {
  const s = score ?? 0;
  if (s >= 70) return "strong";
  if (s >= 50) return "good";
  return "weak";
}

export interface BandCounts {
  strong: number;
  good: number;
  weak: number;
  total: number;
}

export function bandCounts(scores: (number | null | undefined)[]): BandCounts {
  const counts: BandCounts = { strong: 0, good: 0, weak: 0, total: 0 };
  for (const s of scores) {
    counts[scoreBand(s)] += 1;
    counts.total += 1;
  }
  return counts;
}
