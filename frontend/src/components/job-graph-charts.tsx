"use client";

import { useMemo } from "react";
import type { GraphJob } from "@/lib/types";
import { fitColor, GRAPH_COLOR, BAND_COLOR } from "@/lib/graph-bands";
import { jobsWithBothStages, rerankPairs } from "@/lib/graph-insights";

/**
 * Analytical companion charts to the constellation and rank-flow hero. Pure
 * SVG, no extra deps, all colored from the shared token helper. Per-job marks
 * call `onSelect` so the page's shared detail panel updates; hover uses native
 * <title> tooltips (the persistent detail lives in the panel).
 */

interface SelectProps {
  jobs: GraphJob[];
  selectedId?: string | null;
  onSelect?: (jobId: string) => void;
}

// ---------------------------------------------------------------------------
// RankFlow (hero): cosine rank → LLM rank
// ---------------------------------------------------------------------------

export function RankFlow({ jobs, selectedId, onSelect }: SelectProps) {
  const data = useMemo(() => rerankPairs(jobs), [jobs]);

  if (data.length === 0) return <Empty label="No jobs have both a cosine and an LLM score yet." />;

  const W = 680;
  const H = Math.max(220, 60 + data.length * 34);
  const padX = 150;
  const padY = 40;
  const n = data.length;
  const yAt = (rank: number) =>
    padY + (n <= 1 ? (H - padY * 2) / 2 : ((rank - 1) / (n - 1)) * (H - padY * 2));
  const leftX = padX;
  const rightX = W - padX;

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Slope chart connecting each job's cosine rank to its LLM-fit rank"
      >
        <text x={leftX} y={20} textAnchor="middle" fontSize={12} fontWeight={500} fill={GRAPH_COLOR.muted}>
          Cosine rank
        </text>
        <text x={rightX} y={20} textAnchor="middle" fontSize={12} fontWeight={500} fill={GRAPH_COLOR.muted}>
          LLM-fit rank
        </text>
        {data.map(({ job, cosRank, llmRank, delta }) => {
          const color = delta > 0 ? BAND_COLOR.strong : delta < 0 ? BAND_COLOR.weak : GRAPH_COLOR.muted;
          const selected = selectedId === job.job_id;
          return (
            <g
              key={job.job_id}
              style={{ cursor: "pointer" }}
              opacity={selectedId && !selected ? 0.35 : 1}
              onClick={() => onSelect?.(job.job_id)}
            >
              <title>{`${job.title} — cosine #${cosRank} → LLM #${llmRank}`}</title>
              <line
                x1={leftX}
                y1={yAt(cosRank)}
                x2={rightX}
                y2={yAt(llmRank)}
                stroke={color}
                strokeWidth={selected ? 3 : 1.5}
              />
              <circle cx={leftX} cy={yAt(cosRank)} r={4} fill={color} />
              <circle cx={rightX} cy={yAt(llmRank)} r={4} fill={color} />
              <text x={leftX - 10} y={yAt(cosRank) + 4} textAnchor="end" fontSize={12} fill={GRAPH_COLOR.text}>
                {job.title.length > 20 ? job.title.slice(0, 19) + "…" : job.title}
              </text>
              <text x={rightX + 10} y={yAt(llmRank) + 4} textAnchor="start" fontSize={12} fill={GRAPH_COLOR.muted}>
                #{llmRank}
              </text>
            </g>
          );
        })}
      </svg>
      <Legend
        items={[
          ["promoted by LLM", BAND_COLOR.strong],
          ["demoted", BAND_COLOR.weak],
          ["unchanged", GRAPH_COLOR.muted],
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stage-agreement scatter: cosine (x) vs LLM fit (y)
// ---------------------------------------------------------------------------

export function ScatterAgreement({ jobs, selectedId, onSelect }: SelectProps) {
  const data = useMemo(() => jobsWithBothStages(jobs), [jobs]);

  const W = 480;
  const H = 360;
  const pad = 44;
  const x = (cos: number) => pad + cos * (W - pad * 2);
  const y = (llm: number) => H - pad - (llm / 100) * (H - pad * 2);

  if (data.length === 0) return <Empty label="No jobs have both cosine and LLM scores yet." />;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Scatter of cosine similarity versus LLM fit">
      <Grid pad={pad} w={W} h={H} xLabel="cosine similarity →" yLabel="LLM fit →" />
      <line
        x1={x(0)}
        y1={y(0)}
        x2={x(1)}
        y2={y(100)}
        stroke={GRAPH_COLOR.muted}
        strokeWidth={1}
        strokeDasharray="4 4"
        opacity={0.4}
      />
      {data.map((j) => {
        const cos = j.similarity as number;
        const llm = j.score as number;
        const selected = selectedId === j.job_id;
        return (
          <g
            key={j.job_id}
            opacity={selectedId && !selected ? 0.2 : 1}
            onClick={() => onSelect?.(j.job_id)}
            style={{ cursor: "pointer" }}
          >
            <title>{`${j.title} — cosine ${Math.round(cos * 100)}, LLM ${Math.round(llm)}`}</title>
            <circle
              cx={x(cos)}
              cy={y(llm)}
              r={selected ? 8 : 5}
              fill={fitColor(llm)}
              fillOpacity={0.7}
              stroke={selected ? GRAPH_COLOR.accent : fitColor(llm)}
              strokeWidth={1.5}
            />
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Skill-gap bars: aggregate matched/gaps across jobs
// ---------------------------------------------------------------------------

export function SkillGapBars({ jobs }: { jobs: GraphJob[] }) {
  const { gaps, matched } = useMemo(() => {
    const gapCount = new Map<string, number>();
    const matchCount = new Map<string, number>();
    const norm = (s: string) => s.trim().toLowerCase();
    for (const j of jobs) {
      for (const g of j.gaps) gapCount.set(norm(g), (gapCount.get(norm(g)) ?? 0) + 1);
      for (const m of j.matched_skills) matchCount.set(norm(m), (matchCount.get(norm(m)) ?? 0) + 1);
    }
    const top = (m: Map<string, number>) =>
      Array.from(m.entries()).sort((a, b) => b[1] - a[1]).slice(0, 12);
    return { gaps: top(gapCount), matched: top(matchCount) };
  }, [jobs]);

  if (gaps.length === 0 && matched.length === 0)
    return <Empty label="No skill data yet — run the matcher to see matched skills and gaps." />;

  const maxC = Math.max(1, ...gaps.map((g) => g[1]), ...matched.map((m) => m[1]));

  return (
    <div className="grid grid-cols-2 gap-4">
      <BarColumn title="Skills you're missing" entries={gaps} maxC={maxC} color={BAND_COLOR.weak} />
      <BarColumn title="Skills you have (jobs want)" entries={matched} maxC={maxC} color={BAND_COLOR.strong} />
    </div>
  );
}

function BarColumn({
  title,
  entries,
  maxC,
  color,
}: {
  title: string;
  entries: [string, number][];
  maxC: number;
  color: string;
}) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</div>
      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">none</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map(([skill, count]) => (
            <li key={skill} className="flex items-center gap-2">
              <span className="w-24 truncate text-xs capitalize" title={skill}>
                {skill}
              </span>
              <span className="relative h-3 flex-1 overflow-hidden rounded bg-muted/40">
                <span
                  className="absolute inset-y-0 left-0 rounded"
                  style={{ width: `${(count / maxC) * 100}%`, backgroundColor: color }}
                />
              </span>
              <span className="w-6 text-right text-xs tabular-nums text-muted-foreground">{count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Job × skill heatmap
// ---------------------------------------------------------------------------

export function JobSkillHeatmap({ jobs, selectedId, onSelect }: SelectProps) {
  const { matrix, skills } = useMemo(() => {
    const norm = (s: string) => s.trim().toLowerCase();
    const skillSet = new Set<string>();
    for (const j of jobs) {
      j.matched_skills.forEach((s) => skillSet.add(norm(s)));
      j.gaps.forEach((s) => skillSet.add(norm(s)));
    }
    const top = Array.from(skillSet).sort().slice(0, 18);
    const matrix = jobs
      .map((j) => ({
        job: j,
        cells: new Map(
          top.map((s) => {
            const matched = j.matched_skills.some((m) => norm(m) === s);
            const gap = j.gaps.some((g) => norm(g) === s);
            return [s, matched ? "m" : gap ? "g" : "."] as const;
          }),
        ),
      }))
      .sort((a, b) => (b.job.score ?? 0) - (a.job.score ?? 0));
    return { matrix, skills: top };
  }, [jobs]);

  if (skills.length === 0 || matrix.length === 0)
    return <Empty label="No skill data yet — run the matcher to populate matched skills and gaps." />;

  const cell = 20;
  const labelW = 150;
  const W = labelW + skills.length * cell + 8;
  const H = 30 + matrix.length * cell;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ minWidth: W }} role="img" aria-label="Grid of jobs by skill showing matches and gaps">
        {skills.map((s, ci) => (
          <text
            key={s}
            x={labelW + ci * cell + cell / 2}
            y={24}
            textAnchor="start"
            fontSize={9}
            fill={GRAPH_COLOR.muted}
            transform={`rotate(40 ${labelW + ci * cell + cell / 2} 24)`}
          >
            {s.length > 12 ? s.slice(0, 11) + "…" : s}
          </text>
        ))}
        {matrix.map(({ job, cells }, ri) => {
          const selected = selectedId === job.job_id;
          return (
            <g
              key={job.job_id}
              opacity={selectedId && !selected ? 0.4 : 1}
              onClick={() => onSelect?.(job.job_id)}
              style={{ cursor: "pointer" }}
            >
              <title>{`${job.title} — ${job.score ?? "?"}/100`}</title>
              <text
                x={labelW - 6}
                y={30 + ri * cell + cell / 2 + 3}
                textAnchor="end"
                fontSize={9}
                fill={selected ? GRAPH_COLOR.accent : GRAPH_COLOR.text}
              >
                {job.title.length > 22 ? job.title.slice(0, 21) + "…" : job.title}
              </text>
              {skills.map((s, ci) => {
                const v = cells.get(s) ?? ".";
                const fill = v === "m" ? BAND_COLOR.strong : v === "g" ? BAND_COLOR.weak : "transparent";
                return (
                  <rect
                    key={s}
                    x={labelW + ci * cell}
                    y={30 + ri * cell}
                    width={cell - 2}
                    height={cell - 2}
                    rx={3}
                    fill={fill}
                    fillOpacity={v === "." ? 0 : 0.75}
                    stroke={v === "." ? GRAPH_COLOR.axis : fill}
                    strokeWidth={0.5}
                  />
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function Grid({
  pad,
  w,
  h,
  xLabel,
  yLabel,
}: {
  pad: number;
  w: number;
  h: number;
  xLabel: string;
  yLabel: string;
}) {
  return (
    <g>
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke={GRAPH_COLOR.axis} strokeWidth={1} />
      <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke={GRAPH_COLOR.axis} strokeWidth={1} />
      <text x={(w + pad) / 2} y={h - 10} textAnchor="middle" fontSize={11} fill={GRAPH_COLOR.muted}>
        {xLabel}
      </text>
      <text
        x={12}
        y={(h + pad) / 2}
        textAnchor="middle"
        fontSize={11}
        fill={GRAPH_COLOR.muted}
        transform={`rotate(-90 12 ${(h + pad) / 2})`}
      >
        {yLabel}
      </text>
      {[0, 50, 100].map((v) => (
        <text key={v} x={pad - 6} y={h - pad - (v / 100) * (h - pad * 2) + 3} textAnchor="end" fontSize={9} fill={GRAPH_COLOR.muted}>
          {v}
        </text>
      ))}
      {[0, 0.5, 1].map((v) => (
        <text key={v} x={pad + v * (w - pad * 2)} y={h - pad + 12} textAnchor="middle" fontSize={9} fill={GRAPH_COLOR.muted}>
          {v}
        </text>
      ))}
    </g>
  );
}

function Legend({ items }: { items: [string, string][] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
      {items.map(([label, color]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 rounded" style={{ backgroundColor: color }} />
          {label}
        </span>
      ))}
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">{label}</div>
  );
}
