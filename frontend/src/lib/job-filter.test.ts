import { describe, it, expect } from "vitest";
import {
  filterJobs,
  sortJobs,
  jobLocations,
  jobSources,
  isFilterActive,
  DEFAULT_JOB_FILTER,
  SOURCE_LABELS,
  type JobFilterState,
} from "./job-filter";
import type { JobWithScore } from "./types";

function job(p: Partial<JobWithScore>): JobWithScore {
  return {
    id: p.id ?? "1",
    source: p.source ?? "jsearch",
    title: p.title ?? "Engineer",
    company: p.company ?? "ACME",
    location: p.location ?? "Berlin",
    url: p.url ?? null,
    scraped_at: p.scraped_at ?? "2026-06-01T00:00:00Z",
    score: p.score ?? null,
    match_id: p.match_id ?? null,
  };
}

const state = (over: Partial<JobFilterState> = {}): JobFilterState => ({
  ...DEFAULT_JOB_FILTER,
  ...over,
});

describe("filterJobs", () => {
  const jobs = [
    job({ id: "a", title: "Python Developer", company: "ACME", location: "Berlin", score: 87 }),
    job({ id: "b", title: "Backend Engineer", company: "Foo GmbH", location: "Munich", score: 60 }),
    job({ id: "c", title: "Data Engineer", company: "Bar AG", location: "Remote", score: 30 }),
    job({ id: "d", title: "Frontend Dev", company: "ACME", location: "Berlin", score: null }),
  ];

  it("returns everything with the default filter", () => {
    expect(filterJobs(jobs, DEFAULT_JOB_FILTER)).toHaveLength(4);
  });

  it("matches search against title and company, case-insensitively", () => {
    expect(filterJobs(jobs, state({ search: "python" })).map((j) => j.id)).toEqual(["a"]);
    expect(filterJobs(jobs, state({ search: "acme" })).map((j) => j.id)).toEqual(["a", "d"]);
  });

  it("filters by scored / unscored status", () => {
    expect(filterJobs(jobs, state({ status: "unscored" })).map((j) => j.id)).toEqual(["d"]);
    expect(filterJobs(jobs, state({ status: "scored" })).map((j) => j.id)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("filters by match band and excludes unscored jobs", () => {
    expect(filterJobs(jobs, state({ band: "strong" })).map((j) => j.id)).toEqual(["a"]);
    expect(filterJobs(jobs, state({ band: "good" })).map((j) => j.id)).toEqual(["b"]);
    expect(filterJobs(jobs, state({ band: "weak" })).map((j) => j.id)).toEqual(["c"]);
  });

  it("filters by exact location", () => {
    expect(filterJobs(jobs, state({ location: "Berlin" })).map((j) => j.id)).toEqual([
      "a",
      "d",
    ]);
  });

  it("combines multiple filters (AND)", () => {
    const r = filterJobs(jobs, state({ location: "Berlin", status: "scored" }));
    expect(r.map((j) => j.id)).toEqual(["a"]);
  });

  it("does not mutate the input array", () => {
    const copy = [...jobs];
    filterJobs(jobs, state({ search: "python" }));
    expect(jobs).toEqual(copy);
  });

  it("filters by exact source", () => {
    const mixed = [
      job({ id: "a", source: "jsearch" }),
      job({ id: "b", source: "arbeitsagentur" }),
      job({ id: "c", source: "jsearch" }),
    ];
    expect(filterJobs(mixed, state({ source: "arbeitsagentur" })).map((j) => j.id)).toEqual([
      "b",
    ]);
  });

  it("ANDs source with other filters", () => {
    const mixed = [
      job({ id: "a", source: "jsearch", location: "Berlin" }),
      job({ id: "b", source: "arbeitsagentur", location: "Berlin" }),
      job({ id: "c", source: "jsearch", location: "Munich" }),
    ];
    expect(
      filterJobs(mixed, state({ source: "jsearch", location: "Berlin" })).map((j) => j.id),
    ).toEqual(["a"]);
  });
});

describe("sortJobs", () => {
  const jobs = [
    job({ id: "a", title: "Beta", score: 50, scraped_at: "2026-06-01T00:00:00Z" }),
    job({ id: "b", title: "alpha", score: 90, scraped_at: "2026-06-03T00:00:00Z" }),
    job({ id: "c", title: "Gamma", score: null, scraped_at: "2026-06-02T00:00:00Z" }),
  ];

  it("sorts by newest scraped_at by default", () => {
    expect(sortJobs(jobs, "newest").map((j) => j.id)).toEqual(["b", "c", "a"]);
  });

  it("sorts by score descending with nulls last", () => {
    expect(sortJobs(jobs, "score_desc").map((j) => j.id)).toEqual(["b", "a", "c"]);
  });

  it("sorts by score ascending with nulls last", () => {
    expect(sortJobs(jobs, "score_asc").map((j) => j.id)).toEqual(["a", "b", "c"]);
  });

  it("sorts by title A→Z case-insensitively", () => {
    expect(sortJobs(jobs, "title").map((j) => j.id)).toEqual(["b", "a", "c"]);
  });

  it("does not mutate the input array", () => {
    const copy = [...jobs];
    sortJobs(jobs, "score_desc");
    expect(jobs).toEqual(copy);
  });
});

describe("jobLocations", () => {
  it("returns distinct, sorted, non-empty locations", () => {
    const jobs = [
      job({ location: "Munich" }),
      job({ location: "Berlin" }),
      job({ location: "Berlin" }),
      job({ location: null }),
      job({ location: "" }),
    ];
    expect(jobLocations(jobs)).toEqual(["Berlin", "Munich"]);
  });
});

describe("jobSources", () => {
  it("returns distinct, sorted, non-empty sources", () => {
    const jobs = [
      job({ source: "jsearch" }),
      job({ source: "arbeitsagentur" }),
      job({ source: "jsearch" }),
      job({ source: "" }),
    ];
    expect(jobSources(jobs)).toEqual(["arbeitsagentur", "jsearch"]);
  });

  it("maps known raw sources to human labels", () => {
    expect(SOURCE_LABELS.arbeitsagentur).toBe("Bundesagentur für Arbeit");
    expect(SOURCE_LABELS.jsearch).toBe("JSearch");
  });
});

describe("isFilterActive", () => {
  it("is false for the default filter", () => {
    expect(isFilterActive(DEFAULT_JOB_FILTER)).toBe(false);
  });

  it("is true when any dimension is set", () => {
    expect(isFilterActive(state({ search: "x" }))).toBe(true);
    expect(isFilterActive(state({ status: "scored" }))).toBe(true);
    expect(isFilterActive(state({ band: "strong" }))).toBe(true);
    expect(isFilterActive(state({ location: "Berlin" }))).toBe(true);
    expect(isFilterActive(state({ source: "jsearch" }))).toBe(true);
  });
});
