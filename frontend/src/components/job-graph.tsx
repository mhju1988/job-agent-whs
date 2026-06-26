"use client";

import { useEffect, useRef, useState } from "react";
import type { GraphJob } from "@/lib/types";
import {
  pickFit,
  radiusForFit,
  stableAngles,
  type GraphStage,
} from "@/lib/graph-insights";
import { fitColor, GRAPH_COLOR } from "@/lib/graph-bands";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { ChipList } from "@/components/chip-list";

/**
 * Single deterministic radial constellation of jobs around the CV.
 *
 * Each job gets a STABLE angle (by sorted id) so it keeps its bearing across
 * stages; only the radius — `(1 − fit) · MAX_R` — changes when the stage
 * toggles. Positions are deterministic (no Math.random), so the layout is
 * identical on every reload. Toggling the stage tweens node + edge positions
 * with requestAnimationFrame so you watch the LLM re-rank; under
 * prefers-reduced-motion the new positions are applied instantly.
 */

const W = 540;
const H = 540;
const MAX_R = 200;
const CX = W / 2;
const CY = H / 2;
const DURATION_MS = 600;

const STAGES: { value: GraphStage; label: string }[] = [
  { value: 1, label: "Stage 1 · cosine" },
  { value: 2, label: "Stage 2 · LLM fit" },
];

interface Placed {
  job: GraphJob;
  fit: number;
  x: number;
  y: number;
}

interface Pt {
  x: number;
  y: number;
}

export interface JobGraphProps {
  jobs: GraphJob[];
  selectedId?: string | null;
  onSelect?: (jobId: string) => void;
}

export default function JobGraph({ jobs, selectedId, onSelect }: JobGraphProps) {
  const [stage, setStage] = useState<GraphStage>(2);
  const [hovered, setHovered] = useState<string | null>(null);
  const reduced = useReducedMotion();

  // Deterministic target positions for the active stage.
  const angles = stableAngles(jobs);
  const targets: Placed[] = [];
  for (const job of jobs) {
    const fit = pickFit(job, stage);
    if (fit == null) continue;
    const angle = angles.get(job.job_id) ?? 0;
    const r = radiusForFit(fit, MAX_R);
    targets.push({ job, fit, x: CX + Math.cos(angle) * r, y: CY + Math.sin(angle) * r });
  }

  // Animated positions (source of truth in a ref; a counter forces a re-render
  // each frame). Render falls back to the target when a node has no animated
  // position yet, so the first paint is already correct.
  const posRef = useRef<Map<string, Pt>>(new Map());
  const rafRef = useRef<number | null>(null);
  const [, setFrame] = useState(0);

  // Re-run the tween only when the target positions actually change.
  const sig = targets
    .map((t) => `${t.job.job_id}:${t.x.toFixed(1)},${t.y.toFixed(1)}`)
    .join("|");

  useEffect(() => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);

    const targetMap = new Map<string, Pt>(targets.map((t) => [t.job.job_id, { x: t.x, y: t.y }]));
    const start = new Map<string, Pt>();
    targetMap.forEach((tgt, id) => start.set(id, posRef.current.get(id) ?? { ...tgt }));

    if (reduced) {
      posRef.current = targetMap;
      setFrame((f) => f + 1);
      return;
    }

    const t0 = performance.now();
    const ease = (u: number) => 1 - Math.pow(1 - u, 3); // easeOutCubic
    const run = (now: number) => {
      const u = Math.min(1, (now - t0) / DURATION_MS);
      const e = ease(u);
      const next = new Map<string, Pt>();
      targetMap.forEach((tgt, id) => {
        const s = start.get(id) ?? tgt;
        next.set(id, { x: s.x + (tgt.x - s.x) * e, y: s.y + (tgt.y - s.y) * e });
      });
      posRef.current = next;
      setFrame((f) => f + 1);
      if (u < 1) rafRef.current = requestAnimationFrame(run);
    };
    rafRef.current = requestAnimationFrame(run);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, reduced]);

  const draw = targets.map((t) => {
    const p = posRef.current.get(t.job.job_id) ?? { x: t.x, y: t.y };
    return { ...t, x: p.x, y: p.y };
  });

  const active = hovered ?? selectedId ?? null;
  const hoveredJob = hovered ? jobs.find((j) => j.job_id === hovered) : null;
  const hoveredFit = hoveredJob ? pickFit(hoveredJob, stage) ?? 0 : 0;

  return (
    <div className="relative h-full w-full">
      <div className="mb-2 flex justify-end">
        <div className="flex rounded-md border border-border/60 bg-muted/30 text-xs">
          {STAGES.map((s) => (
            <button
              key={s.value}
              onClick={() => setStage(s.value)}
              className={`px-3 py-1.5 font-medium transition-colors first:rounded-l-[calc(theme(borderRadius.md)-1px)] last:rounded-r-[calc(theme(borderRadius.md)-1px)] ${
                stage === s.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-[calc(100%-2.5rem)] w-full"
        style={{ touchAction: "none" }}
      >
        {[0.33, 0.66, 1].map((f) => (
          <circle
            key={f}
            cx={CX}
            cy={CY}
            r={MAX_R * f}
            fill="none"
            stroke={GRAPH_COLOR.axis}
            strokeWidth={1}
            strokeOpacity={0.5}
          />
        ))}

        {draw.map((p) => {
          const dim = active != null && active !== p.job.job_id;
          return (
            <line
              key={`e-${p.job.job_id}`}
              x1={CX}
              y1={CY}
              x2={p.x}
              y2={p.y}
              stroke={fitColor(p.fit)}
              strokeWidth={0.5 + (p.fit / 100) * 2.5}
              strokeOpacity={dim ? 0.08 : 0.25 + (p.fit / 100) * 0.5}
            />
          );
        })}

        <g>
          <circle cx={CX} cy={CY} r={16} fill={GRAPH_COLOR.accent} fillOpacity={0.18} />
          <circle cx={CX} cy={CY} r={16} fill="none" stroke={GRAPH_COLOR.accent} strokeWidth={1.5} />
          <circle cx={CX} cy={CY} r={11} fill="none" stroke={GRAPH_COLOR.accent} strokeWidth={0.8} strokeDasharray="2 3" />
          <text
            x={CX}
            y={CY + 4}
            textAnchor="middle"
            fontSize={11}
            fontWeight={700}
            fill={GRAPH_COLOR.accent}
            style={{ pointerEvents: "none", userSelect: "none" }}
          >
            YOU
          </text>
        </g>

        {draw.map((p) => {
          const color = fitColor(p.fit);
          const r = 4 + (p.fit / 100) * 7;
          const dim = active != null && active !== p.job.job_id;
          const selected = selectedId === p.job.job_id;
          const title = p.job.title;
          const label = title.length <= 22 ? title : title.slice(0, 21) + "…";
          return (
            <g
              key={p.job.job_id}
              transform={`translate(${p.x},${p.y})`}
              opacity={dim ? 0.25 : 1}
              style={{ cursor: "pointer", transition: "opacity 0.2s ease" }}
              onMouseEnter={() => setHovered(p.job.job_id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onSelect?.(p.job.job_id)}
            >
              <circle r={r} fill={color} fillOpacity={0.9} />
              <circle r={r} fill="none" stroke={selected ? GRAPH_COLOR.accent : color} strokeWidth={selected ? 2 : 1} />
              <text
                y={r + 12}
                textAnchor="middle"
                fontSize={9.5}
                fontWeight={500}
                fill={GRAPH_COLOR.text}
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {label}
              </text>
            </g>
          );
        })}
      </svg>

      {hoveredJob && (
        <div className="pointer-events-none absolute left-1/2 top-12 z-10 w-60 -translate-x-1/2 rounded-lg border border-border bg-popover/95 p-3 shadow-lg backdrop-blur">
          <div className="truncate font-display text-sm font-semibold">{hoveredJob.title}</div>
          {hoveredJob.company && (
            <div className="truncate text-xs text-muted-foreground">{hoveredJob.company}</div>
          )}
          <div className="mt-1.5 flex items-baseline gap-2 text-[11px]">
            <span className="font-mono font-semibold" style={{ color: fitColor(hoveredFit) }}>
              {Math.round(hoveredFit)}
            </span>
            <span className="text-muted-foreground">{stage === 1 ? "cosine" : "LLM fit"} / 100</span>
          </div>
          {stage === 2 && (hoveredJob.matched_skills.length > 0 || hoveredJob.gaps.length > 0) && (
            <div className="mt-2 space-y-1.5">
              <ChipList items={hoveredJob.matched_skills.slice(0, 6)} tone="match" />
              <ChipList items={hoveredJob.gaps.slice(0, 6)} tone="gap" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
