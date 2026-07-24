"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Job } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminJobsPage() {
  const qc = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<Job | null>(null);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: api.getJobs,
  });

  const del = useMutation({
    mutationFn: (id: string) => api.deleteJobAdmin(id),
    onSuccess: () => {
      toast.success("Job removed");
      qc.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Delete failed"),
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Job moderation" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Job moderation" />
        <EmptyState icon={Briefcase} title="No jobs in the shared pool" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Admin"
        title="Job moderation"
        description="Remove bad scrapes or duplicates from the shared job pool."
      />
      <div className="space-y-3">
        {jobs.map((j) => (
          <Card key={j.id} className="flex items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <p className="truncate font-medium">{j.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {j.company ?? "Unknown company"} · {j.source}
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={() => setPendingDelete(j)}>
              <Trash2 className="mr-1 h-4 w-4" />
              Remove
            </Button>
          </Card>
        ))}
      </div>
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Remove this job listing?"
        description={pendingDelete?.title ?? ""}
        confirmLabel="Remove"
        destructive
        onConfirm={() => {
          if (pendingDelete) del.mutate(pendingDelete.id);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
