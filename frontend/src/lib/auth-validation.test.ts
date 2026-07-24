import { describe, it, expect, vi, afterEach } from "vitest";
import { passwordsMatch, isSignupDisabledError, fetchSignupAllowed } from "./auth-validation";

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

describe("isSignupDisabledError", () => {
  it("detects the error code Supabase returns when signups are off", () => {
    expect(isSignupDisabledError({ code: "signup_disabled" })).toBe(true);
  });

  it("falls back to the message, since older clients omit the code", () => {
    expect(isSignupDisabledError({ message: "Signups not allowed for this instance" })).toBe(true);
  });

  it("matches the message regardless of casing", () => {
    expect(isSignupDisabledError({ message: "SIGNUPS NOT ALLOWED for this instance" })).toBe(true);
  });

  it("is false for an unrelated auth error", () => {
    expect(isSignupDisabledError({ code: "user_already_exists", message: "User already registered" })).toBe(
      false,
    );
  });

  it("is false for a weak-password error that also mentions signup", () => {
    expect(isSignupDisabledError({ message: "Password should be at least 6 characters" })).toBe(false);
  });

  it("is false for null or undefined", () => {
    expect(isSignupDisabledError(null)).toBe(false);
    expect(isSignupDisabledError(undefined)).toBe(false);
  });
});

describe("fetchSignupAllowed", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubFetch(impl: unknown) {
    vi.stubGlobal("fetch", impl);
  }

  it("is false when the project has signups disabled", async () => {
    stubFetch(vi.fn().mockResolvedValue({ ok: true, json: async () => ({ disable_signup: true }) }));
    await expect(fetchSignupAllowed("https://p.supabase.co", "anon")).resolves.toBe(false);
  });

  it("is true when the project accepts signups", async () => {
    stubFetch(vi.fn().mockResolvedValue({ ok: true, json: async () => ({ disable_signup: false }) }));
    await expect(fetchSignupAllowed("https://p.supabase.co", "anon")).resolves.toBe(true);
  });

  it("calls the settings endpoint with the apikey header", async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ disable_signup: false }) });
    stubFetch(f);
    await fetchSignupAllowed("https://p.supabase.co", "anon-key");
    expect(f).toHaveBeenCalledWith(
      "https://p.supabase.co/auth/v1/settings",
      expect.objectContaining({ headers: { apikey: "anon-key" } }),
    );
  });

  it("fails open — assumes signups are allowed when the request errors", async () => {
    stubFetch(vi.fn().mockRejectedValue(new Error("offline")));
    await expect(fetchSignupAllowed("https://p.supabase.co", "anon")).resolves.toBe(true);
  });

  it("fails open on a non-ok response", async () => {
    stubFetch(vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }));
    await expect(fetchSignupAllowed("https://p.supabase.co", "anon")).resolves.toBe(true);
  });

  it("fails open when config is missing, rather than blocking the form", async () => {
    stubFetch(vi.fn());
    await expect(fetchSignupAllowed("", "")).resolves.toBe(true);
  });
});
