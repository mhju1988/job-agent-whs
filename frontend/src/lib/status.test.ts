import { describe, it, expect } from "vitest";
import { canTransition } from "./status";

describe("canTransition", () => {
  it("allows a valid forward move", () => {
    expect(canTransition("new", "ready_to_send")).toBe(true);
    expect(canTransition("applied", "interview")).toBe(true);
    expect(canTransition("interview", "offer")).toBe(true);
  });

  it("rejects skipping a stage", () => {
    expect(canTransition("new", "applied")).toBe(false);
    expect(canTransition("ready_to_send", "interview")).toBe(false);
  });

  it("rejects moving backward", () => {
    expect(canTransition("applied", "new")).toBe(false);
    expect(canTransition("offer", "interview")).toBe(false);
  });

  it("rejects any move out of a terminal state", () => {
    expect(canTransition("rejected", "applied")).toBe(false);
  });

  it("rejects a no-op move to the same status", () => {
    expect(canTransition("applied", "applied")).toBe(false);
  });
});
