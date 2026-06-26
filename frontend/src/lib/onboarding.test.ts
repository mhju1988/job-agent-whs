import { describe, it, expect } from "vitest";
import { onboardingSteps, onboardingComplete } from "./onboarding";

describe("onboardingSteps", () => {
  it("returns three steps in order", () => {
    const steps = onboardingSteps({ hasProfile: false, jobsCount: 0, scoredCount: 0 });
    expect(steps.map((s) => s.key)).toEqual(["profile", "jobs", "scores"]);
  });

  it("marks done flags from the input", () => {
    const steps = onboardingSteps({ hasProfile: true, jobsCount: 5, scoredCount: 0 });
    expect(steps.find((s) => s.key === "profile")?.done).toBe(true);
    expect(steps.find((s) => s.key === "jobs")?.done).toBe(true);
    expect(steps.find((s) => s.key === "scores")?.done).toBe(false);
  });

  it("treats zero counts as not done", () => {
    const steps = onboardingSteps({ hasProfile: false, jobsCount: 0, scoredCount: 0 });
    expect(steps.every((s) => !s.done)).toBe(true);
  });
});

describe("onboardingComplete", () => {
  it("is true only when all three are satisfied", () => {
    expect(onboardingComplete({ hasProfile: true, jobsCount: 1, scoredCount: 1 })).toBe(true);
  });

  it("is false when any step is missing", () => {
    expect(onboardingComplete({ hasProfile: false, jobsCount: 1, scoredCount: 1 })).toBe(false);
    expect(onboardingComplete({ hasProfile: true, jobsCount: 0, scoredCount: 1 })).toBe(false);
    expect(onboardingComplete({ hasProfile: true, jobsCount: 1, scoredCount: 0 })).toBe(false);
  });
});
