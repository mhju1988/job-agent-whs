import { describe, it, expect } from "vitest";
import { backgroundThemeFor, DEFAULT_BACKGROUND_THEME } from "./background-theme";

describe("backgroundThemeFor", () => {
  it("maps each top-level section to its own theme", () => {
    expect(backgroundThemeFor("/")).toBe("dashboard");
    expect(backgroundThemeFor("/jobs")).toBe("jobs");
    expect(backgroundThemeFor("/matches")).toBe("matches");
    expect(backgroundThemeFor("/graph")).toBe("graph");
    expect(backgroundThemeFor("/applications")).toBe("applications");
    expect(backgroundThemeFor("/profile")).toBe("profile");
    expect(backgroundThemeFor("/observability")).toBe("observability");
  });

  it("lets nested routes inherit their section theme", () => {
    expect(backgroundThemeFor("/applications/123")).toBe("applications");
    expect(backgroundThemeFor("/jobs/some-slug")).toBe("jobs");
    expect(backgroundThemeFor("/observability/run/abc")).toBe("observability");
  });

  it("is case-insensitive on the section segment", () => {
    expect(backgroundThemeFor("/Jobs")).toBe("jobs");
    expect(backgroundThemeFor("/PROFILE")).toBe("profile");
  });

  it("falls back to the default theme for auth and unknown routes", () => {
    expect(backgroundThemeFor("/login")).toBe(DEFAULT_BACKGROUND_THEME);
    expect(backgroundThemeFor("/signup")).toBe(DEFAULT_BACKGROUND_THEME);
    expect(backgroundThemeFor("/styleguide")).toBe(DEFAULT_BACKGROUND_THEME);
    expect(backgroundThemeFor("/totally/unknown")).toBe(DEFAULT_BACKGROUND_THEME);
  });

  it("falls back to the default theme for malformed input", () => {
    expect(backgroundThemeFor("")).toBe(DEFAULT_BACKGROUND_THEME);
    expect(backgroundThemeFor("jobs")).toBe(DEFAULT_BACKGROUND_THEME); // not absolute
    expect(backgroundThemeFor("   ")).toBe(DEFAULT_BACKGROUND_THEME);
  });
});
