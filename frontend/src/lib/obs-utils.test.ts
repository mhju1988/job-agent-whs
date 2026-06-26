import { describe, it, expect } from "vitest";
import { formatDuration, formatLatency, formatCost } from "./obs-utils";

describe("formatDuration", () => {
  it("formats seconds under 60", () => {
    expect(formatDuration("2026-06-17T10:00:00Z", "2026-06-17T10:00:04Z")).toBe("4s");
  });
  it("formats minutes and seconds at 60+", () => {
    expect(formatDuration("2026-06-17T10:00:00Z", "2026-06-17T10:01:23Z")).toBe("1m 23s");
  });
  it("rounds to nearest second", () => {
    expect(formatDuration("2026-06-17T10:00:00.000Z", "2026-06-17T10:00:04.600Z")).toBe("5s");
  });
  it("returns dash for invalid date strings", () => {
    expect(formatDuration("not-a-date", "2026-06-17T10:00:04Z")).toBe("—");
  });
});

describe("formatLatency", () => {
  it("formats ms under 1000", () => {
    expect(formatLatency(340)).toBe("340 ms");
  });
  it("formats as seconds at 1000+", () => {
    expect(formatLatency(2100)).toBe("2.1 s");
  });
  it("returns dash for null", () => {
    expect(formatLatency(null)).toBe("—");
  });
  it("returns dash for undefined", () => {
    expect(formatLatency(undefined)).toBe("—");
  });
});

describe("formatCost", () => {
  it("formats normal cost with 4 decimal places", () => {
    expect(formatCost(0.0014)).toBe("€0.0014");
  });
  it("shows < €0.001 for tiny values", () => {
    expect(formatCost(0.0005)).toBe("< €0.001");
  });
  it("returns dash for null", () => {
    expect(formatCost(null)).toBe("—");
  });
  it("returns dash for undefined", () => {
    expect(formatCost(undefined)).toBe("—");
  });
  it("returns zero cost for exactly 0", () => {
    expect(formatCost(0)).toBe("€0.00");
  });
});
