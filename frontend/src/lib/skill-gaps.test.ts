import { describe, it, expect } from "vitest";
import { topGaps } from "./skill-gaps";
import type { Match } from "./types";

function match(gaps: string[] | null): Match {
  return {
    id: Math.random().toString(),
    job_id: "j",
    score: 50,
    matched_skills: null,
    gaps,
    rationale: null,
    created_at: null,
  };
}

describe("topGaps", () => {
  it("counts gaps across matches and sorts by frequency", () => {
    const matches = [
      match(["Kubernetes", "Go"]),
      match(["Kubernetes", "Rust"]),
      match(["Kubernetes"]),
      match(["Go"]),
    ];
    expect(topGaps(matches, 3)).toEqual([
      { skill: "Kubernetes", count: 3 },
      { skill: "Go", count: 2 },
      { skill: "Rust", count: 1 },
    ]);
  });

  it("merges gaps case-insensitively but keeps first-seen casing", () => {
    const matches = [match(["Docker"]), match(["docker"]), match(["DOCKER"])];
    expect(topGaps(matches, 5)).toEqual([{ skill: "Docker", count: 3 }]);
  });

  it("breaks frequency ties alphabetically", () => {
    const matches = [match(["Zig"]), match(["Ada"])];
    expect(topGaps(matches, 5)).toEqual([
      { skill: "Ada", count: 1 },
      { skill: "Zig", count: 1 },
    ]);
  });

  it("respects the limit", () => {
    const matches = [match(["A"]), match(["B"]), match(["C"])];
    expect(topGaps(matches, 2)).toHaveLength(2);
  });

  it("ignores null/empty gaps and blank strings", () => {
    expect(topGaps([match(null), match([]), match(["  "])], 5)).toEqual([]);
  });
});
