/** Trim, drop empties, dedup preserving first-seen order. UX-side convenience;
 *  the server re-normalizes authoritatively. */
export function normalizeSkills(input: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of input) {
    const s = raw.trim();
    if (s && !seen.has(s)) {
      seen.add(s);
      out.push(s);
    }
  }
  return out;
}
