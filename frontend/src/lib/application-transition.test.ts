import { describe, it, expect } from "vitest";
import { applyOptimisticTransition } from "./application-transition";
import type { Application, ApplicationStatus } from "./types";

function makeApp(id: string, status: ApplicationStatus): Application {
  return {
    id,
    job_id: null,
    job_title: "Dev",
    job_company: "Acme",
    status,
    cover_letter_path: null,
    cv_variant_path: null,
    follow_up_at: null,
    applied_at: null,
  };
}

describe("applyOptimisticTransition", () => {
  it("applies an allowed forward move", () => {
    const out = applyOptimisticTransition([makeApp("a", "new")], "a", "ready_to_send");
    expect(out[0].status).toBe("ready_to_send");
  });

  it("is a no-op for an illegal move (status unchanged)", () => {
    const out = applyOptimisticTransition([makeApp("a", "new")], "a", "applied");
    expect(out[0].status).toBe("new");
  });

  it("is a no-op for an unknown id", () => {
    const out = applyOptimisticTransition([makeApp("a", "new")], "zzz", "ready_to_send");
    expect(out[0].status).toBe("new");
  });

  it("leaves other cards untouched and does not mutate the input", () => {
    const apps = [makeApp("a", "new"), makeApp("b", "applied")];
    const out = applyOptimisticTransition(apps, "a", "ready_to_send");
    expect(out.find((x) => x.id === "b")!.status).toBe("applied");
    expect(apps[0].status).toBe("new"); // input not mutated
  });
});
