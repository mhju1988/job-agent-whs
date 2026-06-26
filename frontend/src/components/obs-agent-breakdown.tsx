import type { AgentStat } from "@/lib/obs-agents";
import { agentDot } from "@/lib/agent-meta";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Per-agent run counts + success-rate mini bars. Renders nothing when empty. */
export function ObsAgentBreakdown({ stats }: { stats: AgentStat[] }) {
  if (stats.length === 0) return null;

  return (
    <Card className="mb-6 border-border/80 bg-card/70 p-5">
      <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        By agent
      </h2>
      <div className="mt-3 space-y-2.5">
        {stats.map((s) => (
          <div key={s.agent} className="flex items-center gap-3">
            <span className={cn("h-2 w-2 shrink-0 rounded-full", agentDot(s.agent))} />
            <span className="w-20 shrink-0 text-sm font-medium capitalize">{s.agent}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-status-offer"
                style={{ width: `${s.successRate}%` }}
              />
            </div>
            <span className="w-24 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {s.success}/{s.total} · {s.successRate}%
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
