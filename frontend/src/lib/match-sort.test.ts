import { describe, expect, it } from "vitest";
import { sortMatches } from "./match-sort";
import type { Match } from "./types";

const m = (id: string, score: number | null, created_at: string | null): Match =>
  ({ id, job_id: id, score, matched_skills: null, gaps: null, rationale: null, created_at }) as Match;

describe("sortMatches", () => {
  const rows = [m("a", 60, "2026-01-02"), m("b", 90, "2026-01-01"), m("c", 30, "2026-01-03")];

  it("high_low sorts by score descending", () => {
    expect(sortMatches(rows, "high_low").map((x) => x.id)).toEqual(["b", "a", "c"]);
  });
  it("low_high sorts by score ascending", () => {
    expect(sortMatches(rows, "low_high").map((x) => x.id)).toEqual(["c", "a", "b"]);
  });
  it("recent sorts by created_at descending", () => {
    expect(sortMatches(rows, "recent").map((x) => x.id)).toEqual(["c", "a", "b"]);
  });
  it("null scores sink to the bottom in high_low", () => {
    const withNull = [m("x", null, "2026-01-01"), m("y", 50, "2026-01-01")];
    expect(sortMatches(withNull, "high_low").map((x) => x.id)).toEqual(["y", "x"]);
  });
  it("null scores sink to the bottom in low_high", () => {
    const withNull = [m("x", null, "2026-01-01"), m("y", 50, "2026-01-01")];
    expect(sortMatches(withNull, "low_high").map((x) => x.id)).toEqual(["y", "x"]);
  });
  it("null/empty created_at sinks to the bottom in recent", () => {
    const withNull = [m("x", 10, null), m("y", 10, "2026-01-01")];
    expect(sortMatches(withNull, "recent").map((x) => x.id)).toEqual(["y", "x"]);
  });
  it("does not mutate the input array", () => {
    const input = [...rows];
    sortMatches(input, "high_low");
    expect(input.map((x) => x.id)).toEqual(["a", "b", "c"]);
  });
});
