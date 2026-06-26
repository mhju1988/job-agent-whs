import { describe, it, expect } from "vitest";
import { summarizeEvents } from "./obs-summary";
import type { ObsEvent } from "./types";

describe("summarizeEvents", () => {
  it("sums tokens, cost, and duration across events", () => {
    const events: ObsEvent[] = [
      { prompt_tokens: 100, completion_tokens: 50, estimated_cost_eur: 0.001, duration_ms: 800 },
      { prompt_tokens: 200, completion_tokens: 30, estimated_cost_eur: 0.002, duration_ms: 1200 },
    ];
    const s = summarizeEvents(events);
    expect(s.calls).toBe(2);
    expect(s.totalTokens).toBe(380);
    expect(s.totalCostEur).toBeCloseTo(0.003);
    expect(s.totalDurationMs).toBe(2000);
  });

  it("takes the first non-null provider and model", () => {
    const events: ObsEvent[] = [
      { provider: null, model: null },
      { provider: "nim", model: "apertus-70b-instruct-2509" },
    ];
    const s = summarizeEvents(events);
    expect(s.provider).toBe("nim");
    expect(s.model).toBe("apertus-70b-instruct-2509");
  });

  it("handles missing fields as zero / null", () => {
    const s = summarizeEvents([{}, {}]);
    expect(s).toEqual({
      calls: 2,
      totalTokens: 0,
      totalCostEur: 0,
      totalDurationMs: 0,
      provider: null,
      model: null,
    });
  });

  it("returns an all-zero summary for no events", () => {
    expect(summarizeEvents([]).calls).toBe(0);
    expect(summarizeEvents([]).provider).toBeNull();
  });
});
