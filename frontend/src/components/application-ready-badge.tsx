import { CheckCircle2 } from "lucide-react";
import type { Match } from "@/lib/types";

/**
 * "Cover letter ready" pill for a match whose job already has a generated
 * application. Mirrors the class-based pill style of ScoreBadge
 * (job-card.tsx) and uses CheckCircle2 — the codebase's canonical
 * success/done icon (see observability + dashboard pages). Returns null
 * when no cover letter has been generated yet, so the surrounding layout
 * collapses cleanly.
 */
export function ApplicationReadyBadge({ match }: { match?: Match | null }) {
  // The application is nested under jobs (matched via jobs.id as the shared
  // FK target of both match_scores.job_id and applications.job_id). PostgREST
  // returns it as a 0-or-1 element array; cover_letter_path is only set once
  // the Writer has run successfully.
  const app = match?.jobs?.applications?.[0];
  if (!app?.cover_letter_path) return null;
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-status-offer/30 bg-status-offer/15 px-2.5 py-0.5 text-xs font-semibold text-status-offer">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Cover letter ready
    </span>
  );
}
