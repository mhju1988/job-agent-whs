"use client";

import type { GraphJob } from "@/lib/types";
import { fitColor } from "@/lib/graph-bands";
import { sharedTerms } from "@/lib/graph-insights";
import { ChipList } from "@/components/chip-list";

/** Shared detail panel for the fit graph: a per-job breakdown of BOTH scoring
 *  stages and their basis. Driven by the page's selected job; clicking a
 *  node/point/row in any visualization populates it. The two stages stack
 *  vertically so they read together in the narrow side column. */
export function JobDetailPanel({
  job,
  cvSkills,
}: {
  job: GraphJob | null;
  cvSkills: string[];
}) {
  if (!job) {
    return (
      <div className="flex h-full min-h-[180px] flex-col items-center justify-center rounded-lg border border-dashed border-border/60 p-6 text-center">
        <span className="text-sm font-medium text-foreground">Click any job to inspect it</span>
        <span className="mt-1 max-w-xs text-xs text-muted-foreground">
          Select a node or point in any chart to see how cosine and the LLM each scored it.
        </span>
      </div>
    );
  }

  const cosine = job.similarity == null ? null : Math.round(job.similarity * 100);
  const llm = job.score == null ? null : Math.round(job.score);
  const shared = sharedTerms(cvSkills, job.requirements);
  const diverges = cosine != null && llm != null && cosine >= 70 && llm < 50;

  return (
    <div className="space-y-4 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <div className="font-display text-base font-semibold">{job.title}</div>
        {job.company && <div className="text-sm text-muted-foreground">{job.company}</div>}
        {diverges && (
          <p className="mt-2 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5 text-xs text-muted-foreground">
            Topically close, but missing key requirements.
          </p>
        )}
      </div>

      {cosine != null && (
        <section className="border-t border-border/60 pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Stage 1 · Cosine
            </span>
            <span className="font-mono text-lg font-semibold" style={{ color: fitColor(cosine) }}>
              {cosine}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Compares your whole CV against the whole posting as vectors — it rewards shared domain
            vocabulary, not specific requirements.
          </p>

          <div className="mt-2.5 text-[11px] font-medium text-foreground">Shared with your CV</div>
          {shared.length > 0 ? (
            <div className="mt-1">
              <ChipList items={shared} tone="match" />
            </div>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">
              No exact term overlap — the match is semantic.
            </p>
          )}

          {(job.requirements.length > 0 || job.description) && (
            <>
              <div className="mt-2.5 text-[11px] font-medium text-foreground">What was compared</div>
              {job.requirements.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {job.requirements.map((req) => (
                    <span
                      key={req}
                      className="rounded-full border border-border/60 bg-muted/40 px-2.5 py-0.5 text-xs text-muted-foreground"
                    >
                      {req}
                    </span>
                  ))}
                </div>
              )}
              {job.description && (
                <p className="mt-1.5 line-clamp-4 text-xs leading-relaxed text-muted-foreground">
                  {job.description}
                </p>
              )}
            </>
          )}

          <p className="mt-2 text-[11px] italic text-muted-foreground/80">
            Cosine compares meaning across the full text, not just matching words.
          </p>
        </section>
      )}

      {llm != null && (
        <section className="border-t border-border/60 pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Stage 2 · LLM fit
            </span>
            <span className="font-mono text-lg font-semibold" style={{ color: fitColor(llm) }}>
              {llm}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Requirement-level gap analysis: which of the job&apos;s requirements you actually meet.
          </p>
          {(job.matched_skills.length > 0 || job.gaps.length > 0) && (
            <div className="mt-2 space-y-1.5">
              <ChipList items={job.matched_skills} tone="match" />
              <ChipList items={job.gaps} tone="gap" />
            </div>
          )}
          {job.rationale && (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{job.rationale}</p>
          )}
        </section>
      )}
    </div>
  );
}
