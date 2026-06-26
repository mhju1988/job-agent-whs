import type { JobWithScore } from "@/lib/types";

export function lastKJobIds(jobs: JobWithScore[], k: number): string[] {
  return [...jobs]
    .sort(
      (a, b) =>
        new Date(b.scraped_at).getTime() - new Date(a.scraped_at).getTime(),
    )
    .slice(0, k)
    .map((j) => j.id);
}
