import type { Profile } from "./types";

/** Scores how complete a CV profile is across six dimensions, and which are
 * still missing — drives the "Profile N%" indicator on the profile page. */
export interface Completeness {
  percent: number;
  missing: string[];
}

export function profileCompleteness(profile: Profile): Completeness {
  const checks: { key: string; ok: boolean }[] = [
    { key: "name", ok: !!profile.full_name?.trim() },
    { key: "summary", ok: !!profile.summary?.trim() },
    { key: "skills", ok: (profile.skills?.length ?? 0) >= 3 },
    { key: "experience", ok: (profile.experience?.length ?? 0) >= 1 },
    { key: "education", ok: (profile.education?.length ?? 0) >= 1 },
    { key: "languages", ok: (profile.languages?.length ?? 0) >= 1 },
  ];

  const satisfied = checks.filter((c) => c.ok).length;
  return {
    percent: Math.round((satisfied / checks.length) * 100),
    missing: checks.filter((c) => !c.ok).map((c) => c.key),
  };
}
