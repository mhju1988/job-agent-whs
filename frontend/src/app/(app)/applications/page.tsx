"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Download, Send, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { applyOptimisticTransition } from "@/lib/application-transition";
import { ALLOWED_TRANSITIONS, STATUS_META, STATUS_ORDER } from "@/lib/status";
import { useSelection } from "@/lib/use-selection";
import type { Application, ApplicationStatus } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { BulkActionBar } from "@/components/bulk-action-bar";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

async function download(id: string, kind: "cover" | "cv") {
  try {
    const blob = await api.downloadDocument(id, kind);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${kind === "cover" ? "cover_letter" : "cv"}_${id}.docx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : "Download failed");
  }
}

function isOverdue(iso: string | null): boolean {
  return !!iso && new Date(iso).getTime() <= Date.now();
}

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const sel = useSelection();
  // ids pending confirmation; null = dialog closed.
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);

  const { data: apps, isLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: api.getApplications,
  });

  const del = useMutation({
    mutationFn: (ids: string[]) => api.deleteApplications(ids),
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: ["applications"] });
      const previous = qc.getQueryData<Application[]>(["applications"]);
      if (previous) {
        const remove = new Set(ids);
        qc.setQueryData<Application[]>(
          ["applications"],
          previous.filter((a) => !remove.has(a.id)),
        );
      }
      return { previous };
    },
    onError: (e, _ids, ctx) => {
      if (ctx?.previous) qc.setQueryData(["applications"], ctx.previous);
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    },
    onSuccess: (_d, ids) =>
      toast.success(`${ids.length} ${ids.length === 1 ? "application" : "applications"} deleted`),
    onSettled: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const confirmDelete = () => {
    if (pendingDelete) {
      del.mutate(pendingDelete);
      sel.exit();
    }
    setPendingDelete(null);
  };

  const transition = useMutation({
    mutationFn: ({ id, target }: { id: string; target: ApplicationStatus }) =>
      api.transition(id, target),
    onMutate: async ({ id, target }) => {
      await qc.cancelQueries({ queryKey: ["applications"] });
      const previous = qc.getQueryData<Application[]>(["applications"]);
      if (previous) {
        qc.setQueryData<Application[]>(
          ["applications"],
          applyOptimisticTransition(previous, id, target),
        );
      }
      return { previous };
    },
    onError: (e, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(["applications"], ctx.previous);
      toast.error(e instanceof ApiError ? e.message : "Transition failed");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const byStatus = (status: ApplicationStatus): Application[] =>
    (apps ?? []).filter((a) => a.status === status);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl">
        <PageHeader eyebrow="Pipeline" title="Applications" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!apps || apps.length === 0) {
    return (
      <div className="mx-auto max-w-6xl">
        <PageHeader eyebrow="Pipeline" title="Applications" />
        <EmptyState
          icon={Send}
          title="No applications yet"
          hint="Prepare an application from the Matches page to start your pipeline."
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          eyebrow="Pipeline"
          title="Applications"
          description="Move each card forward with its buttons as it progresses. Forward-only — you click the final Apply yourself."
        />
        {apps && apps.length > 0 && (
          <Button
            size="sm"
            variant={sel.mode ? "secondary" : "outline"}
            className="mt-1 shrink-0"
            onClick={() => (sel.mode ? sel.exit() : sel.enter())}
          >
            {sel.mode ? "Done" : "Select"}
          </Button>
        )}
      </div>
      <div className="flex gap-4 overflow-x-auto pb-3">
        {STATUS_ORDER.map((status) => {
          const items = byStatus(status);
          return (
            <div
              key={status}
              className="flex w-72 shrink-0 flex-col rounded-xl border border-border/60 bg-card/30 p-3"
            >
              <div className="mb-3 flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: `hsl(var(--status-${STATUS_META[status].key}))` }}
                  />
                  <StatusBadge status={status} />
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {items.length}
                </span>
              </div>
              <div className="space-y-2">
                {items.length === 0 && (
                  <p className="px-1 py-6 text-center text-xs text-muted-foreground/70">
                    —
                  </p>
                )}
                {items.map((app) => (
                  <Card key={app.id} className="border-border/80 bg-card p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex min-w-0 items-start gap-2">
                        {sel.mode && (
                          <input
                            type="checkbox"
                            checked={sel.isSelected(app.id)}
                            onChange={() => sel.toggle(app.id)}
                            aria-label={`Select ${app.job_title ?? "application"}`}
                            className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                          />
                        )}
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {app.job_title ?? "Untitled"}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            {app.job_company ?? "Unknown"}
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        {isOverdue(app.follow_up_at) && (
                          <Bell className="h-4 w-4 text-status-interview" />
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                          aria-label="Delete application"
                          title="Delete application"
                          onClick={() => setPendingDelete([app.id])}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    {ALLOWED_TRANSITIONS[app.status].length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {ALLOWED_TRANSITIONS[app.status].map((target) => (
                          <Button
                            key={target}
                            variant={target === "rejected" ? "ghost" : "default"}
                            size="sm"
                            className="h-7 px-2 text-xs"
                            disabled={transition.isPending}
                            onClick={() => transition.mutate({ id: app.id, target })}
                          >
                            → {STATUS_META[target].label}
                          </Button>
                        ))}
                      </div>
                    )}
                    {(app.cover_letter_path || app.cv_variant_path) && (
                      <div className="mt-2 flex flex-wrap gap-1 border-t border-border/60 pt-2">
                        {app.cover_letter_path && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => download(app.id, "cover")}
                          >
                            <Download className="mr-1 h-3 w-3" /> Letter
                          </Button>
                        )}
                        {app.cv_variant_path && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => download(app.id, "cv")}
                          >
                            <Download className="mr-1 h-3 w-3" /> CV
                          </Button>
                        )}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {sel.mode && (
        <BulkActionBar
          count={sel.count}
          actionLabel={`Delete ${sel.count}`}
          destructive
          onAction={() => setPendingDelete(Array.from(sel.selected))}
          onSelectAll={() => sel.selectAll((apps ?? []).map((a) => a.id))}
          onCancel={sel.exit}
          disabled={del.isPending}
        />
      )}
      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete applications?"
        description={`This removes ${pendingDelete?.length ?? 0} application${
          (pendingDelete?.length ?? 0) === 1 ? "" : "s"
        } and their generated documents. This can't be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
      />
    </div>
  );
}
