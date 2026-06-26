"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Network, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import {
  graphStats,
  rerankHeadline,
  scatterHeadline,
  skillGapHeadline,
  heatmapHeadline,
} from "@/lib/graph-insights";
import { BAND_COLOR } from "@/lib/graph-bands";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import JobGraph from "@/components/job-graph";
import { JobDetailPanel } from "@/components/job-detail-panel";
import {
  RankFlow,
  ScatterAgreement,
  SkillGapBars,
  JobSkillHeatmap,
} from "@/components/job-graph-charts";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const LEGEND = [
  { label: "Strong 70+", color: BAND_COLOR.strong },
  { label: "Good 50–69", color: BAND_COLOR.good },
  { label: "Weak <50", color: BAND_COLOR.weak },
];

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {LEGEND.map((l) => (
        <span key={l.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: l.color }} />
          {l.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "hsl(var(--primary))" }} />
        Your CV
      </span>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-border/80 bg-card/70 p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`mt-1 font-display text-2xl font-semibold ${accent ? "text-primary" : ""}`}>{value}</div>
    </div>
  );
}

function Section({
  title,
  headline,
  children,
}: {
  title: string;
  headline: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-border/80 bg-card/70 p-5">
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      <p className="mb-3 text-sm text-muted-foreground">{headline}</p>
      {children}
    </Card>
  );
}

export default function FitGraphPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["match-graph"],
    queryFn: () => api.getMatchGraph(),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const jobs = data?.jobs ?? [];
  const hasProfile = !!data?.profile;
  const selectedJob = selectedId ? jobs.find((j) => j.job_id === selectedId) ?? null : null;

  if (!isLoading && !hasProfile) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader
          eyebrow="Visualization"
          title="Fit graph"
          description="See how every job relates to your CV across both scoring stages."
        />
        <EmptyState
          icon={Network}
          title="Upload your CV first"
          hint="The fit graph needs a profile to place jobs around. Upload a CV to get scored matches."
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl">
        <PageHeader
          eyebrow="Visualization"
          title="Fit graph"
          description="How your two-stage matcher ranked every job against your CV."
        />
        <Skeleton className="h-[60vh] w-full rounded-lg" />
      </div>
    );
  }

  const stats = graphStats(jobs);
  const strong = [...jobs]
    .filter((j) => (j.score ?? 0) >= 70)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const strongNames = strong.slice(0, 3).map((j) => j.title).join(", ");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        eyebrow="Visualization"
        title="Fit graph"
        description="How your two-stage matcher ranked every job against your CV."
        actions={<Legend />}
      />

      {jobs.length === 0 ? (
        <EmptyState
          icon={Network}
          title="No matches yet"
          hint="Run Scout + Matcher to score jobs against your CV. The graph will populate as matches come in."
        />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Jobs scored" value={stats.scored} />
            <StatCard label="Re-ranked by LLM" value={stats.reranked} />
            <StatCard label="Strong fits" value={stats.strong} accent />
          </div>

          <Section title="The re-rank: cosine → LLM fit" headline={rerankHeadline(jobs)}>
            <RankFlow jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} />
          </Section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="border-border/80 bg-card/70 p-5">
              <h2 className="font-display text-lg font-semibold">Jobs around your CV</h2>
              <p className="mb-3 text-sm text-muted-foreground">
                Closer nodes fit better. Toggle the stage to watch the LLM re-rank.
              </p>
              <div className="h-[60vh] min-h-[420px]">
                <JobGraph jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} />
              </div>
            </Card>
            <div className="lg:pt-2">
              <JobDetailPanel job={selectedJob} cvSkills={data?.profile?.skills ?? []} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Section title="Where the stages disagree" headline={scatterHeadline(jobs)}>
              <ScatterAgreement jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} />
            </Section>
            <Section title="What to learn next" headline={skillGapHeadline(jobs)}>
              <SkillGapBars jobs={jobs} />
            </Section>
          </div>

          <Section title="Job × skill heatmap" headline={heatmapHeadline(jobs)}>
            <JobSkillHeatmap jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} />
          </Section>

          {strong.length > 0 && (
            <div className="flex items-center justify-between gap-4 rounded-lg border border-border/80 bg-card/70 p-5">
              <div>
                <div className="font-display text-base font-semibold">
                  {strong.length} strong fit{strong.length === 1 ? "" : "s"} application-ready
                </div>
                <div className="text-sm text-muted-foreground">{strongNames}</div>
              </div>
              <Link
                href="/matches"
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
              >
                Review strong matches <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}
