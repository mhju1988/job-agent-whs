import { describe, it, expect } from "vitest";
import { scoreBand, bandCounts } from "./match-bands";

describe("scoreBand", () => {
  it("classifies 70 and above as strong", () => {
    expect(scoreBand(70)).toBe("strong");
    expect(scoreBand(92)).toBe("strong");
  });

  it("classifies 50..69 as good", () => {
    expect(scoreBand(50)).toBe("good");
    expect(scoreBand(69)).toBe("good");
  });

  it("classifies below 50 as weak", () => {
    expect(scoreBand(49)).toBe("weak");
    expect(scoreBand(0)).toBe("weak");
  });

  it("treats null/undefined as weak", () => {
    expect(scoreBand(null)).toBe("weak");
    expect(scoreBand(undefined)).toBe("weak");
  });
});

describe("bandCounts", () => {
  it("counts each band and the total", () => {
    const c = bandCounts([85, 72, 60, 55, 40, null]);
    expect(c).toEqual({ strong: 2, good: 2, weak: 2, total: 6 });
  });

  it("returns all zeros for an empty list", () => {
    expect(bandCounts([])).toEqual({ strong: 0, good: 0, weak: 0, total: 0 });
  });
});
