import { describe, it, expect } from "vitest";
import {
  filterRuns,
  runAgents,
  isObsFilterActive,
  DEFAULT_OBS_FILTER,
  type ObsFilterState,
} from "./obs-filter";
import type { ObsRun } from "./types";

function run(p: Partial<ObsRun>): ObsRun {
  return {
    run_id: p.run_id ?? "r",
    agent_name: p.agent_name ?? "scout",
    status: p.status ?? "success",
    started_at: p.started_at ?? "2026-06-18T10:00:00Z",
    finished_at: p.finished_at ?? null,
    error_message: p.error_message ?? null,
  };
}

const state = (over: Partial<ObsFilterState> = {}): ObsFilterState => ({
  ...DEFAULT_OBS_FILTER,
  ...over,
});

const runs = [
  run({ run_id: "1", agent_name: "scout", status: "success" }),
  run({ run_id: "2", agent_name: "matcher", status: "error", error_message: "timeout" }),
  run({ run_id: "3", agent_name: "writer", status: "running" }),
  run({ run_id: "4", agent_name: "matcher", status: "success" }),
];

describe("filterRuns", () => {
  it("returns everything by default", () => {
    expect(filterRuns(runs, DEFAULT_OBS_FILTER)).toHaveLength(4);
  });

  it("filters by agent", () => {
    expect(filterRuns(runs, state({ agent: "matcher" })).map((r) => r.run_id)).toEqual([
      "2",
      "4",
    ]);
  });

  it("filters by success / error status", () => {
    expect(filterRuns(runs, state({ status: "success" })).map((r) => r.run_id)).toEqual([
      "1",
      "4",
    ]);
    expect(filterRuns(runs, state({ status: "error" })).map((r) => r.run_id)).toEqual(["2"]);
  });

  it("treats any non-success/error status as running", () => {
    expect(filterRuns(runs, state({ status: "running" })).map((r) => r.run_id)).toEqual(["3"]);
  });

  it("searches agent name and error message case-insensitively", () => {
    expect(filterRuns(runs, state({ search: "TIMEOUT" })).map((r) => r.run_id)).toEqual(["2"]);
    expect(filterRuns(runs, state({ search: "writer" })).map((r) => r.run_id)).toEqual(["3"]);
  });

  it("does not mutate the input", () => {
    const copy = [...runs];
    filterRuns(runs, state({ agent: "scout" }));
    expect(runs).toEqual(copy);
  });
});

describe("runAgents", () => {
  it("returns distinct sorted agent names", () => {
    expect(runAgents(runs)).toEqual(["matcher", "scout", "writer"]);
  });
});

describe("isObsFilterActive", () => {
  it("is false by default and true when set", () => {
    expect(isObsFilterActive(DEFAULT_OBS_FILTER)).toBe(false);
    expect(isObsFilterActive(state({ agent: "scout" }))).toBe(true);
    expect(isObsFilterActive(state({ status: "error" }))).toBe(true);
    expect(isObsFilterActive(state({ search: "x" }))).toBe(true);
  });
});
