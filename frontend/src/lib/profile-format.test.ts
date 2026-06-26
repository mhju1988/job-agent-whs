import { describe, it, expect } from "vitest";
import { formatDateRange } from "./profile-format";

describe("formatDateRange", () => {
  it("joins start and end with an en-dash", () => {
    expect(formatDateRange("2021", "2024")).toBe("2021 – 2024");
  });

  it("shows 'present' when only start is given", () => {
    expect(formatDateRange("2021", null)).toBe("2021 – present");
    expect(formatDateRange("2021", undefined)).toBe("2021 – present");
  });

  it("shows just the end when only end is given", () => {
    expect(formatDateRange(null, "2024")).toBe("2024");
  });

  it("returns empty string when neither is given", () => {
    expect(formatDateRange(null, null)).toBe("");
    expect(formatDateRange(undefined, undefined)).toBe("");
  });

  it("ignores blank/whitespace values", () => {
    expect(formatDateRange("  ", "2024")).toBe("2024");
    expect(formatDateRange("2021", "  ")).toBe("2021 – present");
  });
});
