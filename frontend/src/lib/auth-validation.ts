/** True when both fields are non-empty and identical. */
export function passwordsMatch(password: string, confirm: string): boolean {
  return password.length > 0 && password === confirm;
}

/**
 * True when a Supabase auth error means "this instance does not accept signups".
 *
 * Returned when the project has `disable_signup` set, which is how access is
 * restricted to demo accounts issued by an admin. Newer clients carry the
 * `signup_disabled` code; older ones only set the message, so both are checked.
 */
export function isSignupDisabledError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const { code, message } = error as { code?: unknown; message?: unknown };
  if (code === "signup_disabled") return true;
  return typeof message === "string" && message.toLowerCase().includes("signups not allowed");
}

/**
 * Ask the Supabase project whether it currently accepts signups.
 *
 * Lets the signup page explain the restriction on arrival instead of after a
 * failed submit. Deliberately **fails open**: this is a UX affordance, not a
 * security control — the real gate is `disable_signup` on the project, which
 * rejects the request regardless of what the UI renders. A network blip must
 * never leave a legitimate user staring at a form they cannot use.
 */
export async function fetchSignupAllowed(supabaseUrl: string, anonKey: string): Promise<boolean> {
  if (!supabaseUrl || !anonKey) return true;
  try {
    const res = await fetch(`${supabaseUrl}/auth/v1/settings`, { headers: { apikey: anonKey } });
    if (!res.ok) return true;
    const settings = (await res.json()) as { disable_signup?: unknown };
    return settings.disable_signup !== true;
  } catch {
    return true;
  }
}
