import { describe, it, expect } from "vitest";
import { passwordsMatch } from "./auth-validation";

describe("passwordsMatch", () => {
  it("is true when both fields are identical and non-empty", () => {
    expect(passwordsMatch("hunter2", "hunter2")).toBe(true);
  });

  it("is false when they differ", () => {
    expect(passwordsMatch("hunter2", "hunter3")).toBe(false);
  });

  it("is false when both are empty", () => {
    expect(passwordsMatch("", "")).toBe(false);
  });
});
