"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import type { OnboardingStep, OnboardingStepKey } from "@/lib/onboarding";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const CTA: Record<
  OnboardingStepKey,
  { label: string; href?: string; smartFind?: boolean }
> = {
  profile: { label: "Upload CV", href: "/profile" },
  jobs: { label: "Smart Find", smartFind: true },
  scores: { label: "Score jobs", href: "/jobs" },
};

/**
 * First-run guidance shown in place of the KPI row until the user has a
 * profile, some jobs, and at least one score. The first incomplete step gets
 * the active call-to-action.
 */
export function OnboardingChecklist({
  steps,
  onSmartFind,
}: {
  steps: OnboardingStep[];
  onSmartFind: () => void;
}) {
  const activeKey = steps.find((s) => !s.done)?.key;
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <Card className="border-primary/30 bg-card/70 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold">Get set up</h2>
          <p className="text-sm text-muted-foreground">
            Three quick steps to your first matches.
          </p>
        </div>
        <span className="text-sm tabular-nums text-muted-foreground">
          {doneCount}/{steps.length}
        </span>
      </div>

      <ol className="mt-5 space-y-2">
        {steps.map((step, i) => {
          const active = step.key === activeKey;
          const cta = CTA[step.key];
          return (
            <li
              key={step.key}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                active
                  ? "border-primary/40 bg-primary/5"
                  : "border-border/60"
              }`}
            >
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-sm font-semibold ${
                  step.done
                    ? "border-status-offer bg-status-offer/15 text-status-offer"
                    : active
                      ? "border-primary text-primary"
                      : "border-border text-muted-foreground"
                }`}
              >
                {step.done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span
                className={`flex-1 text-sm ${
                  step.done
                    ? "text-muted-foreground line-through"
                    : "font-medium text-foreground"
                }`}
              >
                {step.label}
              </span>
              {active &&
                (cta.smartFind ? (
                  <Button size="sm" onClick={onSmartFind}>
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    {cta.label}
                  </Button>
                ) : (
                  <Button asChild size="sm">
                    <Link href={cta.href ?? "/"}>
                      {cta.label}
                      <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                    </Link>
                  </Button>
                ))}
            </li>
          );
        })}
      </ol>

      {activeKey == null && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 text-sm text-status-offer"
        >
          You&apos;re all set — your dashboard is live below. 🎉
        </motion.p>
      )}
    </Card>
  );
}
