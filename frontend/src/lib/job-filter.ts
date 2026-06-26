import type { JobWithScore } from "./types";
import { scoreBand, type Band } from "./match-bands";

export type JobStatus = "all" | "scored" | "unscored";
export type BandFilter = "all" | Band;
export type JobSort = "newest" | "score_desc" | "score_asc" | "title";

export interface JobFilterState {
  search: string;
  status: JobStatus;
  band: BandFilter;
  /** "all" or an exact location string. */
  location: string;
  /** "all" or an exact raw source value. */
  source: string;
}

export const DEFAULT_JOB_FILTER: JobFilterState = {
  search: "",
  status: "all",
  band: "all",
  location: "all",
  source: "all",
};

/** Applies search + status + band + location filters (all ANDed). Pure. */
export function filterJobs(
  jobs: JobWithScore[],
  state: JobFilterState,
): JobWithScore[] {
  const q = state.search.trim().toLowerCase();
  return jobs.filter((j) => {
    if (q) {
      const hay = `${j.title} ${j.company ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (state.status === "scored" && j.score == null) return false;
    if (state.status === "unscored" && j.score != null) return false;
    if (state.band !== "all") {
      // Band only applies to scored jobs; unscored are excluded.
      if (j.score == null || scoreBand(j.score) !== state.band) return false;
    }
    if (state.location !== "all" && j.location !== state.location) return false;
    if (state.source !== "all" && j.source !== state.source) return false;
    return true;
  });
}

/** Returns a new, sorted array. Null scores sort last for both score modes. */
export function sortJobs(jobs: JobWithScore[], sort: JobSort): JobWithScore[] {
  const out = [...jobs];
  switch (sort) {
    case "newest":
      out.sort((a, b) => b.scraped_at.localeCompare(a.scraped_at));
      break;
    case "score_desc":
      out.sort((a, b) => scoreKey(b.score) - scoreKey(a.score));
      break;
    case "score_asc":
      out.sort((a, b) => scoreKeyAsc(a.score) - scoreKeyAsc(b.score));
      break;
    case "title":
      out.sort((a, b) =>
        a.title.toLowerCase().localeCompare(b.title.toLowerCase()),
      );
      break;
  }
  return out;
}

// Descending: higher score first, nulls treated as -1 (last).
function scoreKey(score: number | null): number {
  return score ?? -1;
}

// Ascending: lower score first, but nulls pushed to the end.
function scoreKeyAsc(score: number | null): number {
  return score ?? Number.POSITIVE_INFINITY;
}

/** Human-readable labels for known raw source values. */
export const SOURCE_LABELS: Record<string, string> = {
  arbeitsagentur: "Bundesagentur für Arbeit",
  jsearch: "JSearch",
};

/** Distinct, alphabetically-sorted, non-empty raw source values in the jobs. */
export function jobSources(jobs: JobWithScore[]): string[] {
  const set = new Set<string>();
  for (const j of jobs) {
    const src = j.source?.trim();
    if (src) set.add(src);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

/** Distinct, alphabetically-sorted, non-empty locations present in the jobs. */
export function jobLocations(jobs: JobWithScore[]): string[] {
  const set = new Set<string>();
  for (const j of jobs) {
    const loc = j.location?.trim();
    if (loc) set.add(loc);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

/** True when the filter differs from the default (drives the Clear button). */
export function isFilterActive(state: JobFilterState): boolean {
  return (
    state.search.trim() !== "" ||
    state.status !== "all" ||
    state.band !== "all" ||
    state.location !== "all" ||
    state.source !== "all"
  );
}
