import { describe, expect, it } from "vitest";
import { normalizeSkills } from "./profile-skills";

describe("normalizeSkills", () => {
  it("trims, drops empties, dedups preserving first-seen order", () => {
    expect(normalizeSkills([" Python ", "Python", "", "SQL", "  "])).toEqual(["Python", "SQL"]);
  });
  it("returns [] for all-empty input", () => {
    expect(normalizeSkills(["", "  "])).toEqual([]);
  });
});
