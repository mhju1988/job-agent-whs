"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Briefcase, Search, Sparkles, Target, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { lastKJobIds } from "@/lib/job-utils";
import { useRun } from "@/components/run-drawer";
import {
  filterJobs,
  sortJobs,
  jobLocations,
  jobSources,
  isFilterActive,
  DEFAULT_JOB_FILTER,
  SOURCE_LABELS,
  type JobSort,
  type JobStatus,
  type BandFilter,
} from "@/lib/job-filter";
import type { JobWithScore } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { JobCard } from "@/components/job-card";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const DEPTH = [
  { label: "Quick", value: 10 },
  { label: "Balanced", value: 25 },
  { label: "Thorough", value: 50 },
] as const;
type DepthLabel = (typeof DEPTH)[number]["label"];

export default function JobsPage() {
  const run = useRun();

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: api.getJobs,
  });
  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.getMatches(0),
  });
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const hasProfile = !!me?.has_profile;

  const { data: suggestions = [] } = useQuery({
    queryKey: ["search-suggestions"],
    queryFn: api.getSearchSuggestions,
    enabled: hasProfile,
    staleTime: 24 * 60 * 60 * 1000,
    retry: false,
  });

  const [keyword, setKeyword] = useState("");
  const [location, setLocation] = useState("");
  const [depth, setDepth] = useState<DepthLabel>("Balanced");
  const maxResults = DEPTH.find((d) => d.label === depth)!.value;

  // Seed the search inputs from the top AI suggestion once it resolves (async).
  // One-shot via `seeded`; per-field guards so typing during the load is never
  // clobbered.
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current || suggestions.length === 0) return;
    seeded.current = true;
    const top = suggestions[0];
    if (!keyword && top.keyword) setKeyword(top.keyword);
    if (!location && top.location) setLocation(top.location);
  }, [suggestions, keyword, location]);

  const [filter, setFilter] = useState(DEFAULT_JOB_FILTER);
  const [sort, setSort] = useState<JobSort>("newest");

  const [lastK, setLastK] = useState(3);
  const [scoringJobId, setScoringJobId] = useState<string | null>(null);

  useEffect(() => {
    if (run.status !== "running") setScoringJobId(null);
  }, [run.status]);

  const scoreMap = useMemo(
    () => Object.fromEntries(matches.map((m) => [m.job_id, m])),
    [matches],
  );

  const jobsWithScores: JobWithScore[] = useMemo(
    () =>
      jobs.map((j) => ({
        ...j,
        score: scoreMap[j.id]?.score ?? null,
        match_id: scoreMap[j.id]?.id ?? null,
      })),
    [jobs, scoreMap],
  );

  const unscoredIds = useMemo(
    () => jobsWithScores.filter((j) => j.score == null).map((j) => j.id),
    [jobsWithScores],
  );

  const locations = useMemo(() => jobLocations(jobsWithScores), [jobsWithScores]);
  const sources = useMemo(() => jobSources(jobsWithScores), [jobsWithScores]);
  const visibleJobs = useMemo(
    () => sortJobs(filterJobs(jobsWithScores, filter), sort),
    [jobsWithScores, filter, sort],
  );
  const filterActive = isFilterActive(filter);

  const isRunning = run.status === "running";

  const lastKIds = useMemo(
    () => lastKJobIds(jobsWithScores, lastK),
    [jobsWithScores, lastK],
  );

  const handleScoreLast = () => {
    if (!hasProfile) {
      toast.error("Upload a CV first to score jobs against your profile.");
      return;
    }
    if (lastKIds.length === 0) {
      toast.info("No jobs loaded yet.");
      return;
    }
    run.start("matcher", { job_ids: lastKIds }, "Scoring");
  };

  const handleScoreOne = (jobId: string) => {
    if (!hasProfile) {
      toast.error("Upload a CV first to score jobs against your profile.");
      return;
    }
    setScoringJobId(jobId);
    run.start("matcher", { job_ids: [jobId] }, "Scoring");
  };

  const handleSearch = (kw = keyword, loc = location) =>
    run.start("scout", { keyword: kw, location: loc, max_results: maxResults }, "Search");

  const handleScore = () => {
    if (!hasProfile) {
      toast.error("Upload a CV first to score jobs against your profile.");
      return;
    }
    run.start("matcher", { job_ids: unscoredIds }, "Scoring");
  };

  const handleSmartFind = () => {
    if (!hasProfile) {
      toast.error("Upload a CV first — Smart Find picks the best role from your profile.");
      return;
    }
    run.start("scout-matcher", { location, max_results: maxResults }, "Smart Find");
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Sourcing"
        title="Jobs"
        description="Search for listings, then score them against your CV."
      />

      {suggestions.length > 0 && (
        <div className="mb-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Suggested for you
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={`${s.keyword}|${s.location ?? ""}`}
                title={s.rationale ?? undefined}
                onClick={() => {
                  setKeyword(s.keyword);
                  if (s.location) setLocation(s.location);
                  handleSearch(s.keyword, s.location ?? location);
                }}
                className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
              >
                {s.keyword}
              </button>
            ))}
          </div>
        </div>
      )}

      <Card className="mb-6 border-border/80 bg-card/70 p-5">
        <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div className="space-y-1.5">
            <Label htmlFor="kw">Keywords</Label>
            <Input
              id="kw"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !isRunning && handleSearch()}
              disabled={isRunning}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="loc">Location</Label>
            <Input
              id="loc"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !isRunning && handleSearch()}
              disabled={isRunning}
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={() => handleSearch()} disabled={isRunning} variant="outline">
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
            <Button onClick={handleSmartFind} disabled={isRunning}>
              <Sparkles className="mr-2 h-4 w-4" />
              Smart Find
            </Button>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Depth</span>
          <div className="flex rounded-md border border-border/60 bg-muted/30">
            {DEPTH.map((d) => (
              <button
                key={d.label}
                onClick={() => setDepth(d.label)}
                disabled={isRunning}
                className={`px-3 py-1 text-xs transition-colors first:rounded-l-[calc(theme(borderRadius.md)-1px)] last:rounded-r-[calc(theme(borderRadius.md)-1px)] ${
                  depth === d.label
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-muted-foreground">({maxResults} results)</span>
        </div>
      </Card>

      {jobs.length > 0 && (
        <div className="mb-4 space-y-3">
          {/* Filter / sort toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[180px] flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={filter.search}
                onChange={(e) =>
                  setFilter((f) => ({ ...f, search: e.target.value }))
                }
                placeholder="Filter by title or company…"
                className="pl-8"
                aria-label="Filter jobs"
              />
            </div>
            <Select
              value={filter.status}
              onValueChange={(v) =>
                setFilter((f) => ({ ...f, status: v as JobStatus }))
              }
            >
              <SelectTrigger className="w-[130px]" aria-label="Filter by score status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="scored">Scored</SelectItem>
                <SelectItem value="unscored">Unscored</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filter.band}
              onValueChange={(v) =>
                setFilter((f) => ({ ...f, band: v as BandFilter }))
              }
            >
              <SelectTrigger className="w-[140px]" aria-label="Filter by match band">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All scores</SelectItem>
                <SelectItem value="strong">Strong (70+)</SelectItem>
                <SelectItem value="good">Good (50–69)</SelectItem>
                <SelectItem value="weak">Weak (&lt;50)</SelectItem>
              </SelectContent>
            </Select>
            {locations.length > 0 && (
              <Select
                value={filter.location}
                onValueChange={(v) => setFilter((f) => ({ ...f, location: v }))}
              >
                <SelectTrigger className="w-[150px]" aria-label="Filter by location">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All locations</SelectItem>
                  {locations.map((loc) => (
                    <SelectItem key={loc} value={loc}>
                      {loc}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {sources.length > 1 && (
              <Select
                value={filter.source}
                onValueChange={(v) => setFilter((f) => ({ ...f, source: v }))}
              >
                <SelectTrigger className="w-[180px]" aria-label="Filter by source">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sources</SelectItem>
                  {sources.map((s) => (
                    <SelectItem key={s} value={s}>
                      {SOURCE_LABELS[s] ?? s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Select value={sort} onValueChange={(v) => setSort(v as JobSort)}>
              <SelectTrigger className="w-[160px]" aria-label="Sort jobs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Newest</SelectItem>
                <SelectItem value="score_desc">Score (high → low)</SelectItem>
                <SelectItem value="score_asc">Score (low → high)</SelectItem>
                <SelectItem value="title">Title (A → Z)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Result count + bulk actions */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {filterActive
                  ? `${visibleJobs.length} of ${jobs.length} jobs`
                  : `${jobs.length} ${jobs.length === 1 ? "job" : "jobs"}`}
              </span>
              {filterActive && (
                <button
                  onClick={() => setFilter(DEFAULT_JOB_FILTER)}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X className="h-3 w-3" /> Clear
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {unscoredIds.length > 0 && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleScore}
                  disabled={isRunning}
                >
                  <Sparkles className="mr-2 h-3.5 w-3.5" />
                  Score {unscoredIds.length}{" "}
                  {unscoredIds.length === 1 ? "job" : "jobs"}
                </Button>
              )}
              <div className="flex items-center gap-1">
                <Select
                  value={String(lastK)}
                  onValueChange={(v) => setLastK(Number(v))}
                  disabled={isRunning}
                >
                  <SelectTrigger
                    className="h-8 w-14 border-border/60 bg-muted/30 px-2 text-xs shadow-none"
                    aria-label="Number of recent jobs to score"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={String(n)}>
                        {n}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleScoreLast}
                  disabled={isRunning}
                >
                  <Target className="mr-2 h-3.5 w-3.5" />
                  Score last {lastK}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {jobsLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : jobsWithScores.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No jobs yet"
          hint="Enter keywords and hit Search, or use Smart Find to let AI pick the best role from your CV."
        />
      ) : visibleJobs.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No jobs match your filters"
          hint="Try adjusting or clearing the filters to see more results."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFilter(DEFAULT_JOB_FILTER)}
            >
              <X className="mr-2 h-3.5 w-3.5" />
              Clear filters
            </Button>
          }
        />
      ) : (
        <motion.div layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence>
            {visibleJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                match={scoreMap[job.id]}
                scoring={scoringJobId === job.id}
                disabled={isRunning}
                onScore={handleScoreOne}
              />
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
