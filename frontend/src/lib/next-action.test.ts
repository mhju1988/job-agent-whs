import { describe, it, expect } from "vitest";
import { computeNextAction } from "./next-action";

describe("computeNextAction", () => {
  it("prompts CV upload first when there is no profile", () => {
    const a = computeNextAction({
      hasProfile: false,
      jobsCount: 0,
      unscoredCount: 0,
      strongCount: 0,
    });
    expect(a?.id).toBe("upload-cv");
    expect(a?.kind).toBe("link");
    expect(a?.href).toBe("/profile");
  });

  it("prompts Smart Find when a profile exists but no jobs are loaded", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 0,
      unscoredCount: 0,
      strongCount: 0,
    });
    expect(a?.id).toBe("smart-find");
    expect(a?.kind).toBe("smart-find");
  });

  it("prompts scoring when unscored jobs exist", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 10,
      unscoredCount: 8,
      strongCount: 0,
    });
    expect(a?.id).toBe("score-jobs");
    expect(a?.href).toBe("/jobs");
    expect(a?.message).toContain("8");
  });

  it("uses singular phrasing for one unscored job", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 1,
      unscoredCount: 1,
      strongCount: 0,
    });
    expect(a?.message).toContain("1 job ");
    expect(a?.message).not.toContain("jobs");
  });

  it("prompts reviewing matches when strong matches exist and nothing is unscored", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 10,
      unscoredCount: 0,
      strongCount: 3,
    });
    expect(a?.id).toBe("review-matches");
    expect(a?.href).toBe("/matches");
    expect(a?.message).toContain("3");
  });

  it("returns null when everything is handled", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 10,
      unscoredCount: 0,
      strongCount: 0,
    });
    expect(a).toBeNull();
  });

  it("prioritises unscored jobs over strong matches", () => {
    const a = computeNextAction({
      hasProfile: true,
      jobsCount: 10,
      unscoredCount: 2,
      strongCount: 5,
    });
    expect(a?.id).toBe("score-jobs");
  });
});
