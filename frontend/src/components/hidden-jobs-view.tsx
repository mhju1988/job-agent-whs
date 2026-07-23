"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { JobWithScore } from "@/lib/types";
import { useSelection } from "@/lib/use-selection";
import { JobCard } from "@/components/job-card";
import { BulkActionBar } from "@/components/bulk-action-bar";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** The always-available "restore" surface: lists the caller's hidden jobs and
 *  un-hides them (single + bulk). Un-hiding a job restores it to both the Jobs
 *  list and Matches, since hide is keyed by job. Owns its own selection state so
 *  it never tangles with the active Jobs page's hide-selection. */
export function HiddenJobsView() {
  const qc = useQueryClient();
  const sel = useSelection();

  const { data: hidden = [], isLoading } = useQuery({
    queryKey: ["hidden-jobs"],
    queryFn: api.getHiddenJobs,
  });

  const unhide = useMutation({
    mutationFn: (ids: string[]) => api.unhideJobs(ids),
    onSuccess: (_d, ids) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
      qc.invalidateQueries({ queryKey: ["hidden-jobs"] });
      toast.success(`${ids.length} ${ids.length === 1 ? "job" : "jobs"} restored`);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Restore failed"),
  });

  const handleUnhideOne = (jobId: string) => unhide.mutate([jobId]);
  const handleUnhideSelected = () => {
    const ids = Array.from(sel.selected);
    sel.exit();
    unhide.mutate(ids);
  };

  // Hidden jobs carry no score badge (their match_scores are filtered out of
  // /matches; the score returns intact once restored).
  const cards: JobWithScore[] = hidden.map((j) => ({
    ...j,
    score: null,
    match_id: null,
  }));

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full" />
        ))}
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <EmptyState
        icon={EyeOff}
        title="No hidden jobs"
        hint="Jobs you hide from the Jobs or Matches page land here so you can restore them anytime."
      />
    );
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {cards.length} hidden {cards.length === 1 ? "job" : "jobs"}
        </span>
        <Button
          size="sm"
          variant={sel.mode ? "secondary" : "outline"}
          onClick={() => (sel.mode ? sel.exit() : sel.enter())}
        >
          {sel.mode ? "Done" : "Select"}
        </Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            scoring={false}
            disabled={unhide.isPending}
            selectMode={sel.mode}
            selected={sel.isSelected(job.id)}
            onToggleSelect={sel.toggle}
            onUnhide={handleUnhideOne}
          />
        ))}
      </div>
      {sel.mode && (
        <BulkActionBar
          count={sel.count}
          actionLabel={`Unhide ${sel.count}`}
          onAction={handleUnhideSelected}
          onSelectAll={() => sel.selectAll(cards.map((j) => j.id))}
          onCancel={sel.exit}
          disabled={unhide.isPending}
        />
      )}
    </>
  );
}
