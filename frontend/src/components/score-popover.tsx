"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChipList } from "@/components/chip-list";
import type { Match } from "@/lib/types";

/**
 * Wraps a clickable score badge. Clicking opens a small popover explaining the
 * score (matched skills, gaps, rationale). Closes on outside-click or Escape.
 * Self-contained — no popover dependency.
 */
export function ScorePopover({
  match,
  children,
}: {
  match: Match;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const matched = match.matched_skills ?? [];
  const gaps = match.gaps ?? [];

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Why this score?"
        className="cursor-pointer rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {children}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full z-30 mt-2 w-72 rounded-xl border border-border bg-popover p-4 text-left shadow-lg"
          >
            <div className="mb-2 flex items-baseline justify-between">
              <span className="font-display text-sm font-semibold">
                Why {match.score ?? 0}?
              </span>
            </div>
            {matched.length > 0 && (
              <div className="mb-2">
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Matched
                </div>
                <ChipList items={matched} tone="match" />
              </div>
            )}
            {gaps.length > 0 && (
              <div className="mb-2">
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Gaps
                </div>
                <ChipList items={gaps} tone="gap" />
              </div>
            )}
            {match.rationale && (
              <p className="text-xs leading-relaxed text-muted-foreground">
                {match.rationale}
              </p>
            )}
            {matched.length === 0 && gaps.length === 0 && !match.rationale && (
              <p className="text-xs text-muted-foreground">
                No detailed breakdown available for this score.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
