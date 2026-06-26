"use client";

import Link from "next/link";
import { Lightbulb } from "lucide-react";
import type { GapCount } from "@/lib/skill-gaps";
import { Card } from "@/components/ui/card";

/**
 * Surfaces the skills most often flagged as gaps across the user's matches —
 * a concrete hint about what to add to their CV to score better. Renders
 * nothing when there are no gaps.
 */
export function SkillGapInsight({ gaps }: { gaps: GapCount[] }) {
  if (gaps.length === 0) return null;
  const [top, ...rest] = gaps;

  return (
    <Card className="border-border/80 bg-card/70 p-6">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-primary" />
        <h2 className="font-display text-lg font-semibold">Improve your matches</h2>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        Most common gap:{" "}
        <span className="font-semibold text-foreground">{top.skill}</span> —
        flagged in {top.count} {top.count === 1 ? "match" : "matches"}.
      </p>
      {rest.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {rest.map((g) => (
            <span
              key={g.skill}
              className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
              style={{
                color: "hsl(var(--status-interview))",
                backgroundColor: "hsl(var(--status-interview) / 0.12)",
                borderColor: "hsl(var(--status-interview) / 0.3)",
              }}
            >
              {g.skill} · {g.count}
            </span>
          ))}
        </div>
      )}
      <Link
        href="/profile"
        className="mt-4 inline-block text-sm text-primary hover:underline"
      >
        Add skills to your CV →
      </Link>
    </Card>
  );
}
