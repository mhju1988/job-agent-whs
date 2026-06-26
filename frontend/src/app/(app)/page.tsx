"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Activity,
  ArrowRight,
  Bell,
  Briefcase,
  CheckCircle2,
  CircleSlash,
  Loader2,
  Send,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { STATUS_META, STATUS_ORDER } from "@/lib/status";
import { computeNextAction } from "@/lib/next-action";
import { onboardingSteps, onboardingComplete } from "@/lib/onboarding";
import { topGaps } from "@/lib/skill-gaps";
import { greetingFor } from "@/lib/greeting";
import { bandCounts } from "@/lib/match-bands";
import { formatRelativeTime } from "@/lib/relative-time";
import type { Application } from "@/lib/types";
import { useRun } from "@/components/run-drawer";
import { AnimatedNumber } from "@/components/animated-number";
import { ScoreGauge } from "@/components/score-gauge";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { SkillGapInsight } from "@/components/skill-gap-insight";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const Hero3D = dynamic(() => import("@/components/hero-3d"), { ssr: false });

const due = (iso: string | null) => !!iso && new Date(iso).getTime() <= Date.now();

export default function DashboardPage() {
  const run = useRun();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: api.getJobs });
  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.getMatches(0),
  });
  const { data: apps = [] } = useQuery({
    queryKey: ["applications"],
    queryFn: api.getApplications,
  });
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.getRuns });

  const strong = matches.filter((m) => (m.score ?? 0) >= 70).length;
  const followUps = apps.filter((a) => due(a.follow_up_at));
  const appedJobIds = new Set(apps.map((a) => a.job_id).filter(Boolean));
  const unactioned = matches.filter((m) => !appedJobIds.has(m.job_id));
  const topMatches = [...matches].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 3);

  // Onboarding + smart-guidance state.
  const hasProfile = !!me?.has_profile;
  const scoredJobIds = new Set(matches.map((m) => m.job_id));
  const unscoredCount = jobs.filter((j) => !scoredJobIds.has(j.id)).length;
  const scoredCount = matches.filter((m) => m.score != null).length;
  const onboarding = { hasProfile, jobsCount: jobs.length, scoredCount };
  const setupComplete = onboardingComplete(onboarding);
  const nextAction = computeNextAction({
    hasProfile,
    jobsCount: jobs.length,
    unscoredCount,
    strongCount: strong,
  });
  const gaps = topGaps(matches, 3);
  const dist = bandCounts(matches.map((m) => m.score));
  const greeting = greetingFor(new Date());
  const heroName =
    me && !me.profile_label.startsWith("No profile") ? me.profile_label : null;

  const runSmartFind = () =>
    run.start("scout-matcher", { max_results: 10 }, "Smart Scout + Matcher");

  const kpis = [
    { label: "Jobs scouted", value: jobs.length, icon: Briefcase, href: "/jobs" },
    { label: "Strong matches", value: strong, icon: Sparkles, href: "/matches" },
    { label: "Applications", value: apps.length, icon: Send, href: "/applications" },
    { label: "Follow-ups due", value: followUps.length, icon: Bell, href: "/applications" },
  ];

  const pipelineMax = Math.max(1, ...STATUS_ORDER.map((s) => apps.filter((a) => a.status === s).length));

  return (
    <div className="mx-auto max-w-6xl">
      {/* Hero */}
      <div className="relative grid items-center gap-6 overflow-hidden rounded-2xl border border-border/70 bg-card/40 p-6 sm:p-8 lg:grid-cols-[1.3fr_1fr]">
        <div
          aria-hidden
          className="mesh-atmosphere pointer-events-none absolute inset-0 -z-10 opacity-80"
        />
        <div className="animate-fade-up">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Command center
          </p>
          <h1 className="mt-2 font-display text-4xl font-semibold leading-tight tracking-tight">
            {greeting}
            {heroName ? `, ${heroName}` : ""}
          </h1>
          <p className="mt-3 max-w-md text-muted-foreground">
            {nextAction
              ? nextAction.message
              : followUps.length > 0
                ? `${followUps.length} application${followUps.length > 1 ? "s" : ""} need a follow-up, and ${unactioned.length} matches are waiting.`
                : "You're all caught up. Run Scout + Matcher to find more."}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {nextAction && nextAction.kind === "link" ? (
              <Button asChild>
                <Link href={nextAction.href ?? "/"}>
                  {nextAction.ctaLabel}
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
            ) : (
              <Button onClick={runSmartFind}>
                <Sparkles className="mr-1.5 h-4 w-4" />
                {nextAction?.ctaLabel ?? "Smart Scout + Matcher"}
              </Button>
            )}
            <Button asChild variant="outline">
              <Link href="/matches">Review matches</Link>
            </Button>
          </div>
        </div>
        <div className="h-48 w-full sm:h-60 lg:h-64">
          <Hero3D />
        </div>
      </div>

      {/* Onboarding checklist (first run) or KPIs */}
      {!setupComplete ? (
        <div className="mt-6">
          <OnboardingChecklist
            steps={onboardingSteps(onboarding)}
            onSmartFind={runSmartFind}
          />
        </div>
      ) : (
      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map((k, i) => (
          <motion.div
            key={k.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i, duration: 0.4, ease: "easeOut" }}
            whileHover={{ y: -3 }}
          >
            <Link href={k.href}>
              <Card className="card-interactive border-border/80 bg-card/70 p-5">
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground">
                    {k.label}
                  </span>
                  <k.icon className="h-4 w-4 text-primary" />
                </div>
                <div className="mt-2 font-display text-4xl font-semibold">
                  <AnimatedNumber value={k.value} />
                </div>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Left: pipeline + top matches */}
        <div className="space-y-6">
          <Card className="border-border/80 bg-card/70 p-6">
            <h2 className="font-display text-lg font-semibold">Pipeline</h2>
            <p className="text-sm text-muted-foreground">Applications by lifecycle stage.</p>
            <div className="mt-4 space-y-3">
              {STATUS_ORDER.map((s) => {
                const count = apps.filter((a) => a.status === s).length;
                const meta = STATUS_META[s];
                return (
                  <div key={s} className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-xs text-muted-foreground">
                      {meta.label}
                    </span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: `hsl(var(--status-${meta.key}))` }}
                        initial={{ width: 0 }}
                        animate={{ width: `${(count / pipelineMax) * 100}%` }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                      />
                    </div>
                    <span className="w-6 text-right text-sm tabular-nums">{count}</span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="border-border/80 bg-card/70 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold">Top matches</h2>
              <Link href="/matches" className="text-sm text-primary hover:underline">
                View all
              </Link>
            </div>
            {dist.total > 0 && (
              <div className="mt-3">
                <div className="flex h-2 overflow-hidden rounded-full bg-muted">
                  {dist.strong > 0 && (
                    <div
                      className="bg-status-offer"
                      style={{ width: `${(dist.strong / dist.total) * 100}%` }}
                    />
                  )}
                  {dist.good > 0 && (
                    <div
                      className="bg-yellow-500"
                      style={{ width: `${(dist.good / dist.total) * 100}%` }}
                    />
                  )}
                  {dist.weak > 0 && (
                    <div
                      className="bg-status-rejected"
                      style={{ width: `${(dist.weak / dist.total) * 100}%` }}
                    />
                  )}
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {dist.strong} strong · {dist.good} good · {dist.weak} weak
                </p>
              </div>
            )}
            <div className="mt-4 space-y-4">
              {topMatches.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No matches yet — run Scout + Matcher.
                </p>
              )}
              {topMatches.map((m) => (
                <div key={m.id} className="flex items-center gap-4">
                  <ScoreGauge score={m.score ?? 0} size={56} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{m.jobs?.title ?? "Unknown"}</div>
                    <div className="truncate text-sm text-muted-foreground">
                      {m.jobs?.company ?? ""}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      run.start(
                        "writer",
                        {
                          job_id: m.job_id,
                          match_score_id: m.id,
                          matched_skills: m.matched_skills ?? [],
                        },
                        "Writer",
                      )
                    }
                  >
                    Prepare
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right: next actions + activity */}
        <div className="space-y-6">
          <Card className="border-border/80 bg-card/70 p-6">
            <h2 className="font-display text-lg font-semibold">Next actions</h2>
            <div className="mt-4 space-y-2">
              {followUps.length === 0 && unactioned.length === 0 && (
                <p className="text-sm text-muted-foreground">You&apos;re all caught up. 🎯</p>
              )}
              {followUps.slice(0, 4).map((a: Application) => (
                <Link
                  key={a.id}
                  href="/applications"
                  className="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm transition-colors hover:bg-destructive/10"
                >
                  <Bell className="h-4 w-4 shrink-0 text-destructive" />
                  <span className="min-w-0 flex-1 truncate">
                    Follow up: {a.job_title ?? "application"}
                  </span>
                  {a.follow_up_at && (
                    <span className="shrink-0 text-xs font-medium text-destructive">
                      due {formatRelativeTime(a.follow_up_at)}
                    </span>
                  )}
                </Link>
              ))}
              {unactioned.length > 0 && (
                <Link
                  href="/matches"
                  className="flex items-center gap-3 rounded-lg border border-border/60 px-3 py-2 text-sm transition-colors hover:bg-accent"
                >
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="flex-1">
                    {unactioned.length} match{unactioned.length > 1 ? "es" : ""} not yet actioned
                  </span>
                </Link>
              )}
            </div>
          </Card>

          <SkillGapInsight gaps={gaps} />

          <Card className="border-border/80 bg-card/70 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold">Recent activity</h2>
              <Link href="/observability" className="text-sm text-primary hover:underline">
                Observability
              </Link>
            </div>
            <div className="mt-4 space-y-1">
              {runs.length === 0 && (
                <p className="text-sm text-muted-foreground">No agent runs yet.</p>
              )}
              {runs.slice(0, 6).map((r) => (
                <div
                  key={r.run_id}
                  className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                >
                  {r.status === "success" ? (
                    <CheckCircle2 className="h-4 w-4 text-status-offer" />
                  ) : r.status === "error" ? (
                    <CircleSlash className="h-4 w-4 text-status-rejected" />
                  ) : (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                  <span className="flex-1 capitalize">{r.agent_name}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {r.started_at?.slice(11, 19)}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="flex items-center gap-3 border-border/80 bg-card/70 p-5 text-sm text-muted-foreground">
            <Activity className="h-4 w-4 text-primary" />
            Sources: {me?.scout_sources.join(", ") ?? "—"}
          </Card>
        </div>
      </div>
    </div>
  );
}
