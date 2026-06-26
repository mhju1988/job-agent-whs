import { describe, it, expect } from "vitest";
import { profileCompleteness } from "./profile-completeness";

describe("profileCompleteness", () => {
  it("scores a fully populated profile at 100%", () => {
    const r = profileCompleteness({
      full_name: "Max Mustermann",
      summary: "Backend engineer.",
      skills: ["Python", "SQL", "Docker"],
      experience: [{ title: "Dev", company: "X" }],
      education: [{ degree: "BSc", institution: "Uni" }],
      languages: ["German", "English"],
    });
    expect(r.percent).toBe(100);
    expect(r.missing).toEqual([]);
  });

  it("scores an empty profile at 0% and lists everything missing", () => {
    const r = profileCompleteness({});
    expect(r.percent).toBe(0);
    expect(r.missing).toEqual([
      "name",
      "summary",
      "skills",
      "experience",
      "education",
      "languages",
    ]);
  });

  it("scores a half-complete profile at 50%", () => {
    const r = profileCompleteness({
      full_name: "Max",
      summary: "Hi",
      skills: ["Python", "SQL", "Docker"],
    });
    expect(r.percent).toBe(50);
    expect(r.missing).toEqual(["experience", "education", "languages"]);
  });

  it("treats fewer than three skills as incomplete", () => {
    const r = profileCompleteness({ skills: ["Python", "SQL"] });
    expect(r.missing).toContain("skills");
  });

  it("ignores blank name/summary whitespace", () => {
    const r = profileCompleteness({ full_name: "   ", summary: "" });
    expect(r.missing).toContain("name");
    expect(r.missing).toContain("summary");
  });
});
