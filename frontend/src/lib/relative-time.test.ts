import { describe, it, expect } from "vitest";
import { formatRelativeTime } from "./relative-time";

const NOW = new Date("2026-06-17T12:00:00Z").getTime();
const ago = (ms: number) => new Date(NOW - ms).toISOString();

const SEC = 1000;
const MIN = 60 * SEC;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

describe("formatRelativeTime", () => {
  it("shows 'just now' under a minute", () => {
    expect(formatRelativeTime(ago(30 * SEC), NOW)).toBe("just now");
  });

  it("shows minutes under an hour", () => {
    expect(formatRelativeTime(ago(5 * MIN), NOW)).toBe("5m ago");
  });

  it("shows hours under a day", () => {
    expect(formatRelativeTime(ago(3 * HOUR), NOW)).toBe("3h ago");
  });

  it("shows days under a week", () => {
    expect(formatRelativeTime(ago(2 * DAY), NOW)).toBe("2d ago");
  });

  it("falls back to a date for a week or more", () => {
    const iso = ago(10 * DAY);
    expect(formatRelativeTime(iso, NOW)).toBe(new Date(iso).toLocaleDateString());
  });

  it("returns empty string for missing input", () => {
    expect(formatRelativeTime(null, NOW)).toBe("");
    expect(formatRelativeTime(undefined, NOW)).toBe("");
  });
});
