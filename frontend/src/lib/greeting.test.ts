import { describe, it, expect } from "vitest";
import { greetingFor } from "./greeting";

function at(hour: number): Date {
  const d = new Date("2026-06-18T00:00:00");
  d.setHours(hour);
  return d;
}

describe("greetingFor", () => {
  it("says good morning between 5 and 11", () => {
    expect(greetingFor(at(5))).toBe("Good morning");
    expect(greetingFor(at(11))).toBe("Good morning");
  });

  it("says good afternoon between 12 and 17", () => {
    expect(greetingFor(at(12))).toBe("Good afternoon");
    expect(greetingFor(at(17))).toBe("Good afternoon");
  });

  it("says good evening between 18 and 21", () => {
    expect(greetingFor(at(18))).toBe("Good evening");
    expect(greetingFor(at(21))).toBe("Good evening");
  });

  it("says good night between 22 and 4", () => {
    expect(greetingFor(at(22))).toBe("Good night");
    expect(greetingFor(at(4))).toBe("Good night");
    expect(greetingFor(at(0))).toBe("Good night");
  });
});
