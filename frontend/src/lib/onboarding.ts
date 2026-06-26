/** First-run onboarding state for the dashboard: profile → jobs → scores. */

export interface OnboardingInput {
  hasProfile: boolean;
  jobsCount: number;
  scoredCount: number;
}

export type OnboardingStepKey = "profile" | "jobs" | "scores";

export interface OnboardingStep {
  key: OnboardingStepKey;
  label: string;
  done: boolean;
}

export function onboardingSteps(input: OnboardingInput): OnboardingStep[] {
  return [
    { key: "profile", label: "Upload your CV", done: input.hasProfile },
    { key: "jobs", label: "Find jobs", done: input.jobsCount > 0 },
    { key: "scores", label: "Score your matches", done: input.scoredCount > 0 },
  ];
}

export function onboardingComplete(input: OnboardingInput): boolean {
  return onboardingSteps(input).every((s) => s.done);
}
