import type { ObsRun } from "./types";

export type ObsStatusFilter = "all" | "success" | "error" | "running";

export interface ObsFilterState {
  search: string;
  /** "all" or an exact agent name. */
  agent: string;
  status: ObsStatusFilter;
}

export const DEFAULT_OBS_FILTER: ObsFilterState = {
  search: "",
  agent: "all",
  status: "all",
};

/** A run is "running" when its status is neither success nor error. */
function matchesStatus(run: ObsRun, status: ObsStatusFilter): boolean {
  if (status === "all") return true;
  if (status === "running") return run.status !== "success" && run.status !== "error";
  return run.status === status;
}

/** Filters runs by search (agent name + error message), agent, and status. Pure. */
export function filterRuns(runs: ObsRun[], state: ObsFilterState): ObsRun[] {
  const q = state.search.trim().toLowerCase();
  return runs.filter((r) => {
    if (q) {
      const hay = `${r.agent_name} ${r.error_message ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (state.agent !== "all" && r.agent_name !== state.agent) return false;
    if (!matchesStatus(r, state.status)) return false;
    return true;
  });
}

/** Distinct, alphabetically-sorted agent names present in the runs. */
export function runAgents(runs: ObsRun[]): string[] {
  const set = new Set<string>();
  for (const r of runs) if (r.agent_name) set.add(r.agent_name);
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

export function isObsFilterActive(state: ObsFilterState): boolean {
  return (
    state.search.trim() !== "" || state.agent !== "all" || state.status !== "all"
  );
}
