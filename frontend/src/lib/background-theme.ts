/**
 * Maps a route to a background theme key. Pure + framework-agnostic so it is
 * trivially unit-testable (see background-theme.test.ts).
 *
 * The returned key is written onto `<html data-bg="…">` by
 * `<BackgroundThemeSync />`; the matching `[data-bg="…"] .animated-bg`
 * rules in globals.css recolour the drifting blobs per page.
 *
 * Unrecognised routes (login, signup, 404, …) fall back to "default", which
 * keeps the signature electric-lime / cyan / violet look — no per-route rule
 * means the `.animated-bg` defaults apply unchanged.
 */
export const DEFAULT_BACKGROUND_THEME = "default";

/**
 * Per-page background theme keys. Each corresponds to a `[data-bg="…"]`
 * rule in globals.css. Add a new theme by extending both this union and the
 * CSS — keeping them in sync is the contract of this module.
 */
export type BackgroundTheme =
  | "default"
  | "dashboard"
  | "jobs"
  | "matches"
  | "graph"
  | "applications"
  | "profile"
  | "observability";

/**
 * Resolve the background theme for an absolute pathname.
 *
 * @param pathname - an absolute route, e.g. "/jobs" or "/applications/123".
 * @returns the theme key for `data-bg` (always a member of BackgroundTheme).
 */
export function backgroundThemeFor(pathname: string): BackgroundTheme {
  // Normalise: treat empty / non-absolute / root specially.
  if (!pathname || pathname[0] !== "/") return DEFAULT_BACKGROUND_THEME;
  if (pathname === "/") return "dashboard";

  // First path segment drives the theme; nested routes inherit their
  // section's colour (e.g. /applications/123 → applications).
  const segment = pathname.slice(1).split("/")[0]!.toLowerCase();

  switch (segment) {
    case "jobs":
    case "matches":
    case "graph":
    case "applications":
    case "profile":
    case "observability":
      return segment;
    default:
      return DEFAULT_BACKGROUND_THEME;
  }
}
