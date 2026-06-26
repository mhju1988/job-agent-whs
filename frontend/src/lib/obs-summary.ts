import type { ObsEvent } from "./types";

export interface EventSummary {
  calls: number;
  totalTokens: number;
  totalCostEur: number;
  totalDurationMs: number;
  provider: string | null;
  model: string | null;
}

function num(v: unknown): number {
  return typeof v === "number" && !isNaN(v) ? v : 0;
}

function firstString(events: ObsEvent[], key: string): string | null {
  for (const e of events) {
    const v = e[key];
    if (typeof v === "string" && v) return v;
  }
  return null;
}

/** Aggregates an LLM-call event list into per-run totals. Pure. */
export function summarizeEvents(events: ObsEvent[]): EventSummary {
  let totalTokens = 0;
  let totalCostEur = 0;
  let totalDurationMs = 0;
  for (const e of events) {
    totalTokens += num(e.prompt_tokens) + num(e.completion_tokens);
    totalCostEur += num(e.estimated_cost_eur);
    totalDurationMs += num(e.duration_ms);
  }
  return {
    calls: events.length,
    totalTokens,
    totalCostEur,
    totalDurationMs,
    provider: firstString(events, "provider"),
    model: firstString(events, "model"),
  };
}
