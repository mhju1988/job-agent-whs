import { toast } from "sonner";
import type { RunKind } from "./types";

export interface RunResultSummary {
  title: string;
  description?: string;
  href?: string;
  ctaLabel?: string;
}

function num(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function jobsLabel(n: number): string {
  return `${n} ${n === 1 ? "job" : "jobs"}`;
}

/** Pure: turn an agent run's result payload into a human toast summary. */
export function formatRunResult(
  kind: RunKind,
  result: Record<string, unknown>,
): RunResultSummary {
  switch (kind) {
    case "scout": {
      return {
        title: "Search complete",
        description: `Found ${jobsLabel(num(result.upserted))}`,
        href: "/jobs",
        ctaLabel: "View jobs",
      };
    }
    case "matcher": {
      const scored = num(result.scored);
      return {
        title: "Scoring complete",
        description:
          scored === 0 ? "No new jobs to score" : `${jobsLabel(scored)} scored`,
        href: "/matches",
        ctaLabel: "See matches",
      };
    }
    case "scout-matcher": {
      const scout = (result.scout ?? {}) as Record<string, unknown>;
      const matcher = (result.matcher ?? {}) as Record<string, unknown>;
      return {
        title: "Smart Find complete",
        description: `Found ${jobsLabel(num(scout.upserted))} · scored ${num(
          matcher.scored,
        )}`,
        href: "/matches",
        ctaLabel: "See matches",
      };
    }
    case "writer": {
      return {
        title: "Cover letter ready",
        description: "Your application documents are ready.",
        href: "/applications",
        ctaLabel: "View applications",
      };
    }
    case "rescore": {
      const scored = num(result.scored);
      return {
        title: "Re-score complete",
        description:
          scored === 0
            ? "No matches to re-score"
            : `${scored} ${scored === 1 ? "match" : "matches"} re-scored`,
        href: "/matches",
        ctaLabel: "See matches",
      };
    }
  }
}

/**
 * Show a success toast for a completed agent run, with a CTA that navigates
 * to the most relevant page. `onNavigate` is supplied by the caller (router).
 */
export function showRunResultToast(
  kind: RunKind,
  result: Record<string, unknown>,
  onNavigate?: (href: string) => void,
): void {
  const { title, description, href, ctaLabel } = formatRunResult(kind, result);
  toast.success(title, {
    description,
    action:
      href && ctaLabel && onNavigate
        ? { label: ctaLabel, onClick: () => onNavigate(href) }
        : undefined,
  });
}
