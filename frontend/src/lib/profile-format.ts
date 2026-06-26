/** Formats a CV date range like "2021 – present" for the profile timeline. */
export function formatDateRange(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  const s = start?.trim() || "";
  const e = end?.trim() || "";
  if (s && e) return `${s} – ${e}`;
  if (s) return `${s} – present`;
  if (e) return e;
  return "";
}
