"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { scoreBand, bandCounts, type Band } from "@/lib/match-bands";
import { sortMatches, type MatchSort } from "@/lib/match-sort";
import { useRun } from "@/components/run-drawer";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ApplicationReadyBadge } from "@/components/application-ready-badge";
import { ScoreGauge } from "@/components/score-gauge";
import { ChipList } from "@/components/chip-list";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const SORTS = [
  ["high_low", "Score (high → low)"],
  ["low_high", "Score (low → high)"],
  ["recent", "Most recent"],
] as const;

type Filter = "all" | Band;

const BAND_META: Record<Band, { label: string; bar: string }> = {
  strong: { label: "strong", bar: "bg-status-offer" },
  good: { label: "good", bar: "bg-yellow-500" },
  weak: { label: "weak", bar: "bg-status-rejected" },
};

export default function MatchesPage() {
  const run = useRun();
  const [sort, setSort] = useState<MatchSort>("high_low");
  const [filter, setFilter] = useState<Filter>("all");

  // Fetch every match once (server returns the full set, score-desc); band
  // filtering, the distribution, and sorting are all done on the client.
  const { data: matches, isLoading } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.getMatches(0),
  });

  const all = matches ?? [];
  const counts = bandCounts(all.map((m) => m.score));
  const filtered =
    filter === "all" ? all : all.filter((m) => scoreBand(m.score) === filter);
  const visible = sortMatches(filtered, sort);

  const tabs: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "All", count: counts.total },
    { key: "strong", label: "Strong 70+", count: counts.strong },
    { key: "good", label: "Good 50–69", count: counts.good },
    { key: "weak", label: "Weak <50", count: counts.weak },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Fit"
        title="Matches"
        description="Jobs scored against your CV. Prepare an application for the strong fits."
      />

      <Card className="mb-6 border-border/80 bg-card/70 p-5">
        {/* Score distribution */}
        {counts.total > 0 && (
          <div className="mb-5">
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
              {(["strong", "good", "weak"] as Band[]).map((b) =>
                counts[b] > 0 ? (
                  <button
                    key={b}
                    type="button"
                    onClick={() => setFilter(b)}
                    aria-label={`Filter ${BAND_META[b].label}`}
                    className={`${BAND_META[b].bar} cursor-pointer transition-opacity hover:opacity-80`}
                    style={{ width: `${(counts[b] / counts.total) * 100}%` }}
                  />
                ) : null,
              )}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              <span className="text-status-offer">{counts.strong} strong</span>
              {" · "}
              <span className="text-yellow-600 dark:text-yellow-400">
                {counts.good} good
              </span>
              {" · "}
              <span className="text-status-rejected">{counts.weak} weak</span>
            </p>
          </div>
        )}

        {/* Band filters + sort */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-wrap rounded-md border border-border/60 bg-muted/30">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors first:rounded-l-[calc(theme(borderRadius.md)-1px)] last:rounded-r-[calc(theme(borderRadius.md)-1px)] ${
                  filter === t.key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.label}
                <span className="ml-1.5 tabular-nums opacity-70">{t.count}</span>
              </button>
            ))}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sort">Sort by</Label>
            <Select value={sort} onValueChange={(v) => setSort(v as MatchSort)}>
              <SelectTrigger id="sort" className="w-[200px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORTS.map(([v, l]) => (
                  <SelectItem key={v} value={v}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : visible.length > 0 ? (
        <div className="space-y-3">
          {visible.map((m) => (
            <Card
              key={m.id}
              className="flex flex-col gap-4 border-border/80 bg-card/70 p-5 sm:flex-row sm:items-start"
            >
              <ScoreGauge score={m.score ?? 0} />
              <div className="min-w-0 flex-1">
                <div className="font-display text-lg font-semibold">
                  {m.jobs?.title ?? "Unknown title"}
                </div>
                <div className="text-sm text-muted-foreground">
                  {m.jobs?.company ?? "Unknown company"}
                </div>
                <div className="mt-3 space-y-2">
                  <ChipList items={m.matched_skills ?? []} tone="match" />
                  <ChipList items={m.gaps ?? []} tone="gap" />
                </div>
                {m.rationale && (
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {m.rationale}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <ApplicationReadyBadge match={m} />
                <Button
                  onClick={() =>
                    run.start(
                      "writer",
                      {
                        job_id: m.job_id,
                        match_score_id: m.id,
                        matched_skills: m.matched_skills ?? [],
                      },
                      "Writer",
                    )
                  }
                >
                  Write cover letter
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Sparkles}
          title={
            filter === "all"
              ? "No matches yet"
              : `No ${filter} matches`
          }
          hint={
            filter === "all"
              ? "Run Scout + Matcher to score new jobs against your CV."
              : "Try a different band, or score more jobs to widen the pool."
          }
        />
      )}
    </div>
  );
}
