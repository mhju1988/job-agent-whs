"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { computeNextAction, type NextActionId } from "@/lib/next-action";
import { useRun } from "@/components/run-drawer";
import { Button } from "@/components/ui/button";

/**
 * Thin, dismissible "what's next" strip shown across pages (not the dashboard,
 * which has its own hero). Surfaces the single most relevant next step.
 */
export function NextActionBanner() {
  const pathname = usePathname();
  const run = useRun();
  const [dismissed, setDismissed] = useState<Set<NextActionId>>(new Set());

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const { data: jobs = [] } = useQuery({ queryKey: ["jobs"], queryFn: api.getJobs });
  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.getMatches(0),
  });

  // The dashboard has its own guidance hero — keep the banner off it.
  if (pathname === "/") return null;

  const scoredJobIds = new Set(matches.map((m) => m.job_id));
  const unscoredCount = jobs.filter((j) => !scoredJobIds.has(j.id)).length;
  const strongCount = matches.filter((m) => (m.score ?? 0) >= 70).length;

  const action = computeNextAction({
    hasProfile: !!me?.has_profile,
    jobsCount: jobs.length,
    unscoredCount,
    strongCount,
  });

  const visible = action && !dismissed.has(action.id);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key={action.id}
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
          className="mb-5 overflow-hidden"
        >
          <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3">
            <Sparkles className="h-4 w-4 shrink-0 text-primary" />
            <span className="min-w-0 flex-1 text-sm">{action.message}</span>

            {action.kind === "smart-find" ? (
              <Button
                size="sm"
                onClick={() =>
                  run.start("scout-matcher", { max_results: 10 }, "Smart Find")
                }
              >
                {action.ctaLabel}
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Button>
            ) : (
              <Button asChild size="sm">
                <Link href={action.href ?? "/"}>
                  {action.ctaLabel}
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Link>
              </Button>
            )}

            <button
              type="button"
              aria-label="Dismiss"
              onClick={() =>
                setDismissed((prev) => new Set(prev).add(action.id))
              }
              className="shrink-0 cursor-pointer rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
