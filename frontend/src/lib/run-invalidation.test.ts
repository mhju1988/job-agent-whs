import { describe, expect, it } from "vitest";
import { runInvalidationKeys } from "./run-invalidation";

describe("runInvalidationKeys", () => {
  it("scout invalidates jobs + runs", () => {
    expect(runInvalidationKeys("scout")).toEqual([["jobs"], ["runs"]]);
  });
  it("matcher invalidates matches + runs", () => {
    expect(runInvalidationKeys("matcher")).toEqual([["matches"], ["runs"]]);
  });
  it("scout-matcher invalidates jobs + matches + runs", () => {
    expect(runInvalidationKeys("scout-matcher")).toEqual([["jobs"], ["matches"], ["runs"]]);
  });
  it("writer invalidates applications + matches + runs", () => {
    expect(runInvalidationKeys("writer")).toEqual([["applications"], ["matches"], ["runs"]]);
  });
  it("rescore invalidates matches + runs", () => {
    expect(runInvalidationKeys("rescore")).toEqual([["matches"], ["runs"]]);
  });
  it("every kind includes runs", () => {
    for (const kind of ["scout", "matcher", "scout-matcher", "writer", "rescore"] as const) {
      expect(runInvalidationKeys(kind)).toContainEqual(["runs"]);
    }
  });
});
