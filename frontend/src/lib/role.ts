import type { User } from "@supabase/supabase-js";

/** True when the user's app_metadata carries the admin role. app_metadata is
 * only settable via the Supabase service-role key, never by the user. */
export function isAdmin(user: User | null): boolean {
  return user?.app_metadata?.role === "admin";
}

/** Whether to redirect away from the /admin route group: true once the
 * session has finished loading and the caller isn't an admin. */
export function shouldRedirectFromAdmin(state: { loading: boolean; isAdmin: boolean }): boolean {
  return !state.loading && !state.isAdmin;
}
