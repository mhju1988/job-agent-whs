import { describe, it, expect } from "vitest";
import { formatRunResult } from "./run-result-toast";

describe("formatRunResult", () => {
  it("summarises a scout run by jobs found", () => {
    const r = formatRunResult("scout", {
      fetched: 24,
      normalized: 24,
      upserted: 8,
      errors: [],
    });
    expect(r.title).toBe("Search complete");
    expect(r.description).toBe("Found 8 jobs");
    expect(r.href).toBe("/jobs");
  });

  it("uses singular phrasing for a single job", () => {
    const r = formatRunResult("scout", { upserted: 1 });
    expect(r.description).toBe("Found 1 job");
  });

  it("summarises a matcher run by jobs scored", () => {
    const r = formatRunResult("matcher", {
      candidates_considered: 5,
      scored: 5,
      persisted: 5,
      errors: [],
    });
    expect(r.title).toBe("Scoring complete");
    expect(r.description).toBe("5 jobs scored");
    expect(r.href).toBe("/matches");
  });

  it("reports when a matcher run scored nothing", () => {
    const r = formatRunResult("matcher", { scored: 0, persisted: 0 });
    expect(r.description).toBe("No new jobs to score");
  });

  it("combines scout and matcher counts for scout-matcher", () => {
    const r = formatRunResult("scout-matcher", {
      scout: { upserted: 12 },
      matcher: { scored: 4 },
    });
    expect(r.title).toBe("Smart Find complete");
    expect(r.description).toBe("Found 12 jobs · scored 4");
    expect(r.href).toBe("/matches");
  });

  it("describes a writer run", () => {
    const r = formatRunResult("writer", {
      application_id: "a-1",
      cover_letter_path: "/x.docx",
      cv_variant_path: "/y.docx",
      status: "ready_to_send",
    });
    expect(r.title).toBe("Cover letter ready");
    expect(r.href).toBe("/applications");
  });

  it("defaults missing counts to zero without throwing", () => {
    const r = formatRunResult("scout", {});
    expect(r.description).toBe("Found 0 jobs");
  });
});
