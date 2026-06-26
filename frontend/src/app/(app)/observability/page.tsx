"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, CircleSlash, Copy, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDuration, formatLatency, formatCost } from "@/lib/obs-utils";
import { formatRelativeTime } from "@/lib/relative-time";
import {
  filterRuns,
  runAgents,
  isObsFilterActive,
  DEFAULT_OBS_FILTER,
  type ObsStatusFilter,
} from "@/lib/obs-filter";
import { summarizeEvents } from "@/lib/obs-summary";
import { agentBreakdown } from "@/lib/obs-agents";
import { agentDot } from "@/lib/agent-meta";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ObsAgentBreakdown } from "@/components/obs-agent-breakdown";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <CheckCircle2 className="h-4 w-4 text-status-offer" />;
  if (status === "error") return <CircleSlash className="h-4 w-4 text-status-rejected" />;
  return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
}

export default function ObservabilityPage() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: api.getRuns,
    refetchInterval: 5000,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState(DEFAULT_OBS_FILTER);

  const { data: events } = useQuery({
    queryKey: ["run-events", selected],
    queryFn: () => api.getRunEvents(selected as string),
    enabled: !!selected,
    refetchInterval: 5000,
  });

  const allRuns = runs ?? [];
  const total = allRuns.length;
  const ok = allRuns.filter((r) => r.status === "success").length;

  const agents = runAgents(allRuns);
  const stats = agentBreakdown(allRuns);
  const visibleRuns = filterRuns(allRuns, filter);
  const filterActive = isObsFilterActive(filter);
  const summary = summarizeEvents(events ?? []);

  const copyPrompt = (text: string) => {
    navigator.clipboard?.writeText(text).then(
      () => toast.success("Prompt copied"),
      () => toast.error("Couldn't copy"),
    );
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Telemetry"
        title="Observability"
        description="Agent-run history and LLM token usage."
      />

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {[
          ["Total runs", String(total)],
          ["Success rate", total ? `${Math.round((ok / total) * 100)}%` : "—"],
          ["Succeeded", `${ok}/${total}`],
        ].map(([label, value]) => (
          <Card key={label} className="border-border/80 bg-card/70 p-5">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className="mt-2 font-display text-3xl font-semibold tabular-nums">{value}</div>
          </Card>
        ))}
      </div>

      <ObsAgentBreakdown stats={stats} />

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : allRuns.length > 0 ? (
        <>
          {/* Filter toolbar */}
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Input
              value={filter.search}
              onChange={(e) => setFilter((f) => ({ ...f, search: e.target.value }))}
              placeholder="Search agent or error…"
              className="h-9 min-w-[180px] flex-1"
              aria-label="Search runs"
            />
            <Select
              value={filter.agent}
              onValueChange={(v) => setFilter((f) => ({ ...f, agent: v }))}
            >
              <SelectTrigger className="w-[140px]" aria-label="Filter by agent">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All agents</SelectItem>
                {agents.map((a) => (
                  <SelectItem key={a} value={a} className="capitalize">
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={filter.status}
              onValueChange={(v) =>
                setFilter((f) => ({ ...f, status: v as ObsStatusFilter }))
              }
            >
              <SelectTrigger className="w-[130px]" aria-label="Filter by status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="running">Running</SelectItem>
              </SelectContent>
            </Select>
            {filterActive && (
              <button
                onClick={() => setFilter(DEFAULT_OBS_FILTER)}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-3 w-3" /> Clear
              </button>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {filterActive ? `${visibleRuns.length} of ${total}` : `${total} runs`}
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_1.3fr]">
            <Card className="border-border/80 bg-card/70 p-2">
              <div className="max-h-[28rem] space-y-1 overflow-y-auto">
                {visibleRuns.length === 0 ? (
                  <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                    No runs match your filters.
                  </p>
                ) : (
                  visibleRuns.map((r) => (
                    <button
                      key={r.run_id}
                      onClick={() => setSelected(r.run_id)}
                      className={cn(
                        "flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        selected === r.run_id ? "bg-primary/10" : "hover:bg-accent",
                      )}
                    >
                      <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", agentDot(r.agent_name))} />
                      <StatusIcon status={r.status} />
                      <div className="min-w-0 flex-1">
                        <span className="font-medium capitalize">{r.agent_name}</span>
                        {r.status === "error" && r.error_message && (
                          <p className="truncate text-xs text-destructive">{r.error_message}</p>
                        )}
                      </div>
                      <div
                        className="ml-2 shrink-0 text-right font-mono text-xs text-muted-foreground"
                        title={new Date(r.started_at).toLocaleString()}
                      >
                        <div>{formatRelativeTime(r.started_at)}</div>
                        {r.finished_at && (
                          <div>{formatDuration(r.started_at, r.finished_at)}</div>
                        )}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </Card>

            <Card className="border-border/80 bg-card/70 p-5">
              {!selected ? (
                <p className="text-sm text-muted-foreground">← Select a run to inspect its LLM calls.</p>
              ) : (
                <div>
                  {/* Per-run summary strip */}
                  {summary.calls > 0 && (
                    <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-border/60 bg-muted/30 p-3 sm:grid-cols-4">
                      {[
                        ["Calls", String(summary.calls)],
                        ["Tokens", summary.totalTokens.toLocaleString()],
                        ["Cost", formatCost(summary.totalCostEur)],
                        ["Latency", formatLatency(summary.totalDurationMs)],
                      ].map(([label, value]) => (
                        <div key={label}>
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                            {label}
                          </div>
                          <div className="font-mono text-sm font-semibold tabular-nums">{value}</div>
                        </div>
                      ))}
                      {(summary.provider || summary.model) && (
                        <div className="col-span-2 sm:col-span-4">
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                            Model
                          </div>
                          <div className="truncate font-mono text-xs">
                            {[summary.provider, summary.model].filter(Boolean).join(" · ")}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <h3 className="font-display text-lg font-semibold">LLM calls</h3>
                  <div className="mt-3 space-y-2">
                    {events && events.length > 0 ? (
                      events.map((ev, i) => (
                        <div
                          key={`${i}-${String(ev.prompt_snippet ?? "").slice(0, 20)}`}
                          className="rounded-lg border border-border/60 p-3 font-mono text-xs"
                        >
                          <div className="flex items-center justify-between text-muted-foreground">
                            <span>call {i + 1}</span>
                            <div className="flex items-center gap-2">
                              <span>
                                {Number(ev.prompt_tokens ?? 0) + Number(ev.completion_tokens ?? 0)} tok
                              </span>
                              {typeof ev.prompt_snippet === "string" && ev.prompt_snippet && (
                                <button
                                  onClick={() => copyPrompt(String(ev.prompt_snippet))}
                                  aria-label="Copy prompt"
                                  title="Copy prompt"
                                  className="rounded p-0.5 transition-colors hover:bg-accent hover:text-foreground"
                                >
                                  <Copy className="h-3 w-3" />
                                </button>
                              )}
                            </div>
                          </div>
                          <div className="mt-1.5 flex items-center gap-2">
                            {typeof ev.provider === "string" && (
                              <span
                                className={cn(
                                  "rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
                                  ev.provider === "nim"
                                    ? "border-primary/30 bg-primary/10 text-primary"
                                    : "border-border/60 bg-muted text-muted-foreground",
                                )}
                              >
                                {ev.provider}
                              </span>
                            )}
                            <span className="text-muted-foreground">
                              {formatLatency(typeof ev.duration_ms === "number" ? ev.duration_ms : null)}
                            </span>
                            <span className="text-muted-foreground">
                              {formatCost(typeof ev.estimated_cost_eur === "number" ? ev.estimated_cost_eur : null)}
                            </span>
                          </div>
                          {typeof ev.prompt_snippet === "string" && (
                            <p className="mt-1 line-clamp-2 text-muted-foreground/80">
                              {ev.prompt_snippet}
                            </p>
                          )}
                          {typeof ev.response_snippet === "string" && ev.response_snippet && (
                            <p className="mt-1 line-clamp-2 text-muted-foreground/80">
                              <span className="text-muted-foreground">Response: </span>
                              {ev.response_snippet}
                            </p>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No LLM calls recorded (Scout/Tracker have none).
                      </p>
                    )}
                  </div>
                </div>
              )}
            </Card>
          </div>
        </>
      ) : (
        <EmptyState
          icon={Activity}
          title="No runs yet"
          hint="Trigger Scout, Matcher, or Writer and their telemetry appears here."
        />
      )}
    </div>
  );
}
