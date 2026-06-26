/** Computes the single most relevant "what's next" suggestion for the banner. */

export interface NextActionInput {
  hasProfile: boolean;
  jobsCount: number;
  unscoredCount: number;
  /** Matches scoring >= 70. */
  strongCount: number;
}

export type NextActionId =
  | "upload-cv"
  | "smart-find"
  | "score-jobs"
  | "review-matches";

export interface NextAction {
  id: NextActionId;
  message: string;
  ctaLabel: string;
  /** "link" navigates to href; "smart-find" triggers a scout-matcher run. */
  kind: "link" | "smart-find";
  href?: string;
}

export function computeNextAction(input: NextActionInput): NextAction | null {
  const { hasProfile, jobsCount, unscoredCount, strongCount } = input;

  if (!hasProfile) {
    return {
      id: "upload-cv",
      message: "Upload your CV to unlock scoring and cover letter generation.",
      ctaLabel: "Upload CV",
      kind: "link",
      href: "/profile",
    };
  }

  if (jobsCount === 0) {
    return {
      id: "smart-find",
      message: "Run Smart Find to discover jobs that fit your profile.",
      ctaLabel: "Smart Find",
      kind: "smart-find",
    };
  }

  if (unscoredCount > 0) {
    const noun = unscoredCount === 1 ? "job hasn't" : "jobs haven't";
    return {
      id: "score-jobs",
      message: `${unscoredCount} ${noun} been scored yet. Find your best matches.`,
      ctaLabel: "Score jobs",
      kind: "link",
      href: "/jobs",
    };
  }

  if (strongCount > 0) {
    const verb = strongCount === 1 ? "job scores" : "jobs score";
    return {
      id: "review-matches",
      message: `${strongCount} ${verb} above 70 — ready to write a cover letter?`,
      ctaLabel: "See matches",
      kind: "link",
      href: "/matches",
    };
  }

  return null;
}
