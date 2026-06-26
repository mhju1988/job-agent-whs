/** Pure logic for the fit-graph page: stage fit, re-ranking, stats,
 *  data-driven headlines, and deterministic constellation layout. */
import type { GraphJob } from "./types";

export type GraphStage = 1 | 2;

/** 0..100 fit for the active stage, or null if the stage can't score it. */
export function pickFit(job: GraphJob, stage: GraphStage): number | null {
  if (stage === 1) return job.similarity == null ? null : job.similarity * 100;
  return job.score == null ? null : job.score;
}

/** Jobs that carry BOTH stages — required for re-rank/scatter comparisons. */
export function jobsWithBothStages(jobs: GraphJob[]): GraphJob[] {
  return jobs.filter((j) => j.similarity != null && j.score != null);
}

export interface RerankPair {
  job: GraphJob;
  cosRank: number; // 1 = best
  llmRank: number;
  delta: number; // cosRank - llmRank; positive = promoted by the LLM
}

/** Rank jobs that have both stages by cosine and by LLM, then pair the ranks. */
export function rerankPairs(jobs: GraphJob[]): RerankPair[] {
  const both = jobsWithBothStages(jobs);
  const byCos = [...both].sort((a, b) => (b.similarity as number) - (a.similarity as number));
  const byLlm = [...both].sort((a, b) => (b.score as number) - (a.score as number));
  const cosRank = new Map(byCos.map((j, i) => [j.job_id, i + 1]));
  const llmRank = new Map(byLlm.map((j, i) => [j.job_id, i + 1]));
  return both.map((j) => {
    const c = cosRank.get(j.job_id) as number;
    const l = llmRank.get(j.job_id) as number;
    return { job: j, cosRank: c, llmRank: l, delta: c - l };
  });
}

export interface GraphStats {
  scored: number;
  reranked: number;
  strong: number;
}

export function graphStats(jobs: GraphJob[]): GraphStats {
  const reranked = rerankPairs(jobs).filter((p) => p.delta !== 0).length;
  const strong = jobs.filter((j) => (j.score ?? 0) >= 70).length;
  return { scored: jobs.length, reranked, strong };
}

// ---- Headlines -----------------------------------------------------------

export function rerankHeadline(jobs: GraphJob[]): string {
  const pairs = rerankPairs(jobs);
  if (pairs.length === 0)
    return "Run both scoring stages to see how the LLM re-ranks your matches.";
  const top = [...pairs].sort((a, b) => b.delta - a.delta)[0];
  if (top.delta <= 0)
    return "The LLM kept Stage 1's order — cosine already ranked these well.";
  return `Stage 2 promoted ${top.job.title} from #${top.cosRank} to #${top.llmRank}.`;
}

const DISAGREE_THRESHOLD = 25; // |cosine·100 − LLM| beyond this = sharp disagreement

export function scatterHeadline(jobs: GraphJob[]): string {
  const both = jobsWithBothStages(jobs);
  if (both.length === 0) return "No jobs have both a cosine and an LLM score yet.";
  const k = both.filter(
    (j) => Math.abs((j.similarity as number) * 100 - (j.score as number)) > DISAGREE_THRESHOLD,
  ).length;
  if (k === 0) return "Both stages agree on every job.";
  return `Most jobs agree across stages; ${k} disagree sharply.`;
}

/** Gap-skill frequency across jobs (case-insensitive), most common first. */
function gapFrequency(jobs: GraphJob[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const j of jobs) {
    for (const g of j.gaps) {
      const key = g.trim().toLowerCase();
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  const entries: [string, number][] = [];
  counts.forEach((count, key) => {
    entries.push([key, count]);
  });
  return entries.sort((a, b) => b[1] - a[1]);
}

export function skillGapHeadline(jobs: GraphJob[]): string {
  const top = gapFrequency(jobs);
  if (top.length === 0) return "No skill gaps yet — run the matcher to see what to learn.";
  if (top.length === 1) return `${cap(top[0][0])} blocks the most strong fits.`;
  return `${cap(top[0][0])} and ${cap(top[1][0])} block the most strong fits.`;
}

export function heatmapHeadline(jobs: GraphJob[]): string {
  const top = gapFrequency(jobs);
  if (top.length === 0) return "No skill data yet — run the matcher to populate the grid.";
  return `${cap(top[0][0])} is the most common gap across your matches.`;
}

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ---- Deterministic constellation layout ----------------------------------

/** Stable angle (radians) per job, independent of the active stage so nodes
 *  glide only radially when the stage toggles. Sorted by job_id for
 *  determinism across reloads. */
export function stableAngles(jobs: GraphJob[]): Map<string, number> {
  const ids = jobs.map((j) => j.job_id).sort();
  const n = Math.max(1, ids.length);
  return new Map(ids.map((id, i) => [id, (i / n) * Math.PI * 2]));
}

/** Radius for a 0..100 fit: best fit (100) sits at the center, worst at maxR. */
export function radiusForFit(fit: number, maxR: number): number {
  return (1 - fit / 100) * maxR;
}

/** Terms appearing in BOTH the CV skills and the job requirements
 *  (case-insensitive), preserving the job-requirement spelling, deduped.
 *  A readable intuition for cosine proximity — NOT the actual driver
 *  (cosine compares whole-document meaning, not matching words). */
export function sharedTerms(cvSkills: string[], jobRequirements: string[]): string[] {
  const cv = new Set(cvSkills.map((s) => s.trim().toLowerCase()).filter(Boolean));
  const seen = new Set<string>();
  const out: string[] = [];
  for (const req of jobRequirements) {
    const key = req.trim().toLowerCase();
    if (!key || seen.has(key) || !cv.has(key)) continue;
    seen.add(key);
    out.push(req.trim());
  }
  return out;
}
