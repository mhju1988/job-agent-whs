import { describe, it, expect } from "vitest";
import type { User } from "@supabase/supabase-js";
import { isAdmin, shouldRedirectFromAdmin } from "./role";

function makeUser(role?: string): User {
  return { app_metadata: role ? { role } : {} } as User;
}

describe("isAdmin", () => {
  it("is true when app_metadata.role is admin", () => {
    expect(isAdmin(makeUser("admin"))).toBe(true);
  });

  it("is false for a regular user role", () => {
    expect(isAdmin(makeUser("user"))).toBe(false);
  });

  it("is false when app_metadata has no role", () => {
    expect(isAdmin(makeUser())).toBe(false);
  });

  it("is false when there is no user", () => {
    expect(isAdmin(null)).toBe(false);
  });
});

describe("shouldRedirectFromAdmin", () => {
  it("does not redirect while the session is still loading", () => {
    expect(shouldRedirectFromAdmin({ loading: true, isAdmin: false })).toBe(false);
  });

  it("redirects a loaded non-admin", () => {
    expect(shouldRedirectFromAdmin({ loading: false, isAdmin: false })).toBe(true);
  });

  it("does not redirect a loaded admin", () => {
    expect(shouldRedirectFromAdmin({ loading: false, isAdmin: true })).toBe(false);
  });
});
