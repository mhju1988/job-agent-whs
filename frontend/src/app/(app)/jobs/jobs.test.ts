import { describe, it, expect } from "vitest";
import { lastKJobIds } from "@/lib/job-utils";
import type { JobWithScore } from "@/lib/types";

function makeJob(id: string, scraped_at: string): JobWithScore {
  return {
    id,
    source: "jsearch",
    title: "Dev",
    company: null,
    location: null,
    url: null,
    scraped_at,
    score: null,
    match_id: null,
  };
}

describe("lastKJobIds", () => {
  it("returns IDs sorted newest-first, sliced to k", () => {
    const jobs = [
      makeJob("a", "2024-01-01T00:00:00Z"),
      makeJob("b", "2024-01-03T00:00:00Z"),
      makeJob("c", "2024-01-02T00:00:00Z"),
    ];
    expect(lastKJobIds(jobs, 2)).toEqual(["b", "c"]);
  });

  it("returns all IDs when fewer than k jobs exist", () => {
    const jobs = [makeJob("x", "2024-06-01T00:00:00Z")];
    expect(lastKJobIds(jobs, 5)).toEqual(["x"]);
  });

  it("returns empty array for empty input", () => {
    expect(lastKJobIds([], 3)).toEqual([]);
  });

  it("returns empty array when k is 0", () => {
    const jobs = [makeJob("a", "2024-01-01T00:00:00Z")];
    expect(lastKJobIds(jobs, 0)).toEqual([]);
  });

  it("does not mutate the original array", () => {
    const jobs = [
      makeJob("a", "2024-01-01T00:00:00Z"),
      makeJob("b", "2024-01-03T00:00:00Z"),
    ];
    const original = [...jobs];
    lastKJobIds(jobs, 2);
    expect(jobs).toEqual(original);
  });
});
