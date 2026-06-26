import type { ObsRun } from "./types";

export interface AgentStat {
  agent: string;
  total: number;
  success: number;
  /** Percentage 0–100, rounded. */
  successRate: number;
}

/** Groups runs by agent with totals and success rate, sorted by total desc
 * then agent asc. Pure. */
export function agentBreakdown(runs: ObsRun[]): AgentStat[] {
  const byAgent = new Map<string, { total: number; success: number }>();
  for (const r of runs) {
    const acc = byAgent.get(r.agent_name) ?? { total: 0, success: 0 };
    acc.total += 1;
    if (r.status === "success") acc.success += 1;
    byAgent.set(r.agent_name, acc);
  }
  return Array.from(byAgent.entries())
    .map(([agent, { total, success }]) => ({
      agent,
      total,
      success,
      successRate: total ? Math.round((success / total) * 100) : 0,
    }))
    .sort((a, b) => b.total - a.total || a.agent.localeCompare(b.agent));
}
