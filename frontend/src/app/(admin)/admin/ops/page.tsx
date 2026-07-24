"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminOpsPage() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["admin", "observability", "summary"],
    queryFn: api.getAdminObservabilitySummary,
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Ops" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Ops" />
        <EmptyState icon={Activity} title="No agent runs recorded yet" />
      </div>
    );
  }

  const failed = runs.filter((r) => r.status === "error").length;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Admin"
        title="Ops"
        description={`${runs.length} runs across all users, ${failed} failed.`}
      />
      <div className="space-y-2">
        {runs.map((r) => (
          <Card key={r.run_id} className="flex items-center justify-between gap-3 p-3 text-sm">
            <span className="font-mono text-xs text-muted-foreground">{r.run_id}</span>
            <span>{r.agent_name}</span>
            <Badge variant={r.status === "error" ? "destructive" : "secondary"}>
              {r.status}
            </Badge>
          </Card>
        ))}
      </div>
    </div>
  );
}
