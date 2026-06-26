import { describe, it, expect } from "vitest";
import {
  pickFit,
  rerankPairs,
  graphStats,
  rerankHeadline,
  scatterHeadline,
  skillGapHeadline,
  heatmapHeadline,
  stableAngles,
  radiusForFit,
  sharedTerms,
} from "./graph-insights";
import type { GraphJob } from "./types";

function mk(p: Partial<GraphJob> & { job_id: string }): GraphJob {
  return {
    job_id: p.job_id,
    title: p.title ?? p.job_id,
    company: p.company ?? null,
    similarity: p.similarity ?? null,
    score: p.score ?? null,
    requirements: p.requirements ?? [],
    description: p.description ?? null,
    matched_skills: p.matched_skills ?? [],
    gaps: p.gaps ?? [],
    rationale: p.rationale ?? null,
  };
}

describe("pickFit", () => {
  it("scales cosine for stage 1 and uses score for stage 2", () => {
    const j = mk({ job_id: "a", similarity: 0.42, score: 88 });
    expect(pickFit(j, 1)).toBeCloseTo(42);
    expect(pickFit(j, 2)).toBe(88);
  });
  it("returns null when the stage has no value", () => {
    expect(pickFit(mk({ job_id: "a", similarity: null, score: 50 }), 1)).toBeNull();
    expect(pickFit(mk({ job_id: "a", similarity: 0.5, score: null }), 2)).toBeNull();
  });
});

describe("rerankPairs", () => {
  it("computes cosine vs LLM ranks and a promotion delta", () => {
    const jobs = [
      mk({ job_id: "A", similarity: 0.9, score: 50 }),
      mk({ job_id: "B", similarity: 0.5, score: 90 }),
    ];
    const pairs = rerankPairs(jobs);
    const b = pairs.find((p) => p.job.job_id === "B")!;
    const a = pairs.find((p) => p.job.job_id === "A")!;
    expect(b.cosRank).toBe(2);
    expect(b.llmRank).toBe(1);
    expect(b.delta).toBe(1);
    expect(a.delta).toBe(-1);
  });
  it("ignores jobs missing a stage", () => {
    expect(rerankPairs([mk({ job_id: "A", similarity: 0.9, score: null })])).toHaveLength(0);
  });
});

describe("graphStats", () => {
  it("counts scored, re-ranked, and strong jobs", () => {
    const jobs = [
      mk({ job_id: "A", similarity: 0.9, score: 50 }),
      mk({ job_id: "B", similarity: 0.5, score: 90 }),
      mk({ job_id: "C", score: 30 }),
    ];
    expect(graphStats(jobs)).toEqual({ scored: 3, reranked: 2, strong: 1 });
  });
});

describe("headlines", () => {
  it("names the biggest promotion", () => {
    const jobs = [
      mk({ job_id: "A", title: "Alpha", similarity: 0.9, score: 50 }),
      mk({ job_id: "B", title: "Beta", similarity: 0.5, score: 90 }),
    ];
    expect(rerankHeadline(jobs)).toBe("Stage 2 promoted Beta from #2 to #1.");
  });
  it("falls back when no jobs carry both stages", () => {
    expect(rerankHeadline([mk({ job_id: "A", score: 80 })])).toMatch(/Run both scoring stages/);
    expect(scatterHeadline([mk({ job_id: "A", score: 80 })])).toMatch(/both/i);
  });
  it("falls back when the LLM keeps the cosine order", () => {
    const jobs = [
      mk({ job_id: "A", title: "Alpha", similarity: 0.9, score: 90 }),
      mk({ job_id: "B", title: "Beta", similarity: 0.5, score: 50 }),
    ];
    expect(rerankHeadline(jobs)).toBe(
      "The LLM kept Stage 1's order — cosine already ranked these well.",
    );
  });
  it("summarizes skill gaps (case-insensitive)", () => {
    const jobs = [
      mk({ job_id: "A", gaps: ["Docker", "AWS"] }),
      mk({ job_id: "B", gaps: ["docker"] }),
    ];
    expect(skillGapHeadline(jobs)).toBe("Docker and Aws block the most strong fits.");
    expect(heatmapHeadline(jobs)).toBe("Docker is the most common gap across your matches.");
  });
});

describe("constellation layout", () => {
  it("assigns a stable, deterministic angle per job", () => {
    const jobs = [mk({ job_id: "b" }), mk({ job_id: "a" }), mk({ job_id: "c" })];
    const a1 = stableAngles(jobs);
    const a2 = stableAngles([...jobs].reverse());
    expect(a1.get("a")).toBe(a2.get("a"));
    expect(new Set(a1.values()).size).toBe(3);
  });
  it("places better fits nearer the center", () => {
    expect(radiusForFit(100, 200)).toBe(0);
    expect(radiusForFit(0, 200)).toBe(200);
    expect(radiusForFit(50, 200)).toBe(100);
  });
});

describe("sharedTerms", () => {
  it("returns the case-insensitive intersection, preserving requirement spelling", () => {
    expect(sharedTerms(["Python", "react"], ["python", "Go", "React"])).toEqual(["python", "React"]);
  });
  it("dedupes repeated requirements", () => {
    expect(sharedTerms(["aws"], ["AWS", "aws"])).toEqual(["AWS"]);
  });
  it("returns empty when there is no overlap or an input is empty", () => {
    expect(sharedTerms(["python"], ["java"])).toEqual([]);
    expect(sharedTerms([], ["python"])).toEqual([]);
    expect(sharedTerms(["python"], [])).toEqual([]);
  });
});
