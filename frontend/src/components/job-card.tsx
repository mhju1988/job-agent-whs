"use client";

import { motion } from "motion/react";
import { Eye, ExternalLink, EyeOff, Loader2, Target } from "lucide-react";
import type { JobWithScore, Match } from "@/lib/types";
import { formatRelativeTime } from "@/lib/relative-time";
import { ScorePopover } from "@/components/score-popover";
import { ApplicationReadyBadge } from "@/components/application-ready-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Pill showing a 0–100 match score, colour-banded (strong / good / weak). */
export function ScoreBadge({ score }: { score: number }) {
  const cls =
    score >= 70
      ? "bg-status-offer/15 text-status-offer border-status-offer/30"
      : score >= 40
        ? "bg-yellow-500/15 text-yellow-600 border-yellow-500/30 dark:text-yellow-400"
        : "bg-status-rejected/15 text-status-rejected border-status-rejected/30";
  return (
    <span
      className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold tabular-nums ${cls}`}
    >
      {score}
    </span>
  );
}

/** One job rendered as a grid card: score, title, company · location, scrape
 * age, matched-skill chips (when scored), and Score / View actions. */
export function JobCard({
  job,
  match,
  scoring,
  disabled,
  onScore,
  selectMode,
  selected,
  onToggleSelect,
  onHide,
  onUnhide,
}: {
  job: JobWithScore;
  match?: Match;
  scoring: boolean;
  disabled: boolean;
  onScore?: (jobId: string) => void;
  selectMode?: boolean;
  selected?: boolean;
  onToggleSelect?: (jobId: string) => void;
  onHide?: (jobId: string) => void;
  onUnhide?: (jobId: string) => void;
}) {
  const matchedSkills = (match?.matched_skills ?? []).slice(0, 3);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <Card className="card-interactive flex h-full flex-col gap-3 border-border/80 bg-card/70 p-4">
        <div className="flex items-start justify-between gap-3">
          {selectMode && (
            <input
              type="checkbox"
              checked={!!selected}
              onChange={() => onToggleSelect?.(job.id)}
              aria-label={`Select ${job.title}`}
              className="mt-1 h-4 w-4 shrink-0 accent-primary"
            />
          )}
          <div className="min-w-0 flex-1">
            <h3 className="line-clamp-2 font-medium leading-snug">{job.title}</h3>
            <p className="mt-1 truncate text-sm text-muted-foreground">
              {job.company ?? "Unknown company"}
              {job.location ? ` · ${job.location}` : ""}
            </p>
          </div>
          {job.score != null &&
            (match ? (
              <div className="flex shrink-0 flex-col items-end gap-1.5">
                <ScorePopover match={match}>
                  <ScoreBadge score={job.score} />
                </ScorePopover>
                <ApplicationReadyBadge match={match} />
              </div>
            ) : (
              <ScoreBadge score={job.score} />
            ))}
        </div>

        {matchedSkills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {matchedSkills.map((s) => (
              <span
                key={s}
                className="rounded-full border px-2 py-0.5 text-[11px] font-medium"
                style={{
                  color: "hsl(var(--status-offer))",
                  backgroundColor: "hsl(var(--status-offer) / 0.12)",
                  borderColor: "hsl(var(--status-offer) / 0.3)",
                }}
              >
                {s}
              </span>
            ))}
          </div>
        )}

        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground/70">
            {job.scraped_at ? `scraped ${formatRelativeTime(job.scraped_at)}` : ""}
          </span>
          <div className="flex items-center gap-1">
            {onUnhide && (
              <Button
                size="sm"
                variant="ghost"
                className="shrink-0"
                aria-label="Unhide this job"
                title="Unhide this job"
                onClick={() => onUnhide(job.id)}
                disabled={disabled}
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            )}
            {onHide && (
              <Button
                size="sm"
                variant="ghost"
                className="shrink-0"
                aria-label="Hide this job"
                title="Hide this job"
                onClick={() => onHide(job.id)}
                disabled={disabled}
              >
                <EyeOff className="h-3.5 w-3.5" />
              </Button>
            )}
            {onScore && (
              <Button
                size="sm"
                variant="ghost"
                className="shrink-0"
                aria-label="Score this job"
                title="Score this job"
                onClick={() => onScore(job.id)}
                disabled={disabled}
              >
                {scoring ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Target className="h-3.5 w-3.5" />
                )}
              </Button>
            )}
            {job.url && (
              <Button asChild variant="ghost" size="sm" className="shrink-0">
                <a href={job.url} target="_blank" rel="noopener noreferrer">
                  View <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                </a>
              </Button>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
