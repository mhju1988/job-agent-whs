import { describe, it, expect } from "vitest";
import { agentBreakdown } from "./obs-agents";
import type { ObsRun } from "./types";

function run(agent: string, status: string): ObsRun {
  return {
    run_id: Math.random().toString(),
    agent_name: agent,
    status,
    started_at: "2026-06-18T10:00:00Z",
    finished_at: null,
    error_message: null,
  };
}

describe("agentBreakdown", () => {
  it("groups runs by agent with totals and success rate", () => {
    const runs = [
      run("matcher", "success"),
      run("matcher", "error"),
      run("scout", "success"),
      run("scout", "success"),
      run("scout", "success"),
    ];
    expect(agentBreakdown(runs)).toEqual([
      { agent: "scout", total: 3, success: 3, successRate: 100 },
      { agent: "matcher", total: 2, success: 1, successRate: 50 },
    ]);
  });

  it("sorts by total descending then agent ascending", () => {
    const runs = [run("writer", "success"), run("scout", "success")];
    expect(agentBreakdown(runs).map((a) => a.agent)).toEqual(["scout", "writer"]);
  });

  it("returns an empty array for no runs", () => {
    expect(agentBreakdown([])).toEqual([]);
  });
});
