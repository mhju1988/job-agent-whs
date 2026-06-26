"use client";

export function ScoreGauge({ score, size = 88 }: { score: number; size?: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const off = c * (1 - clamped / 100);
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg viewBox="0 0 80 80" className="-rotate-90" style={{ width: size, height: size }}>
        <circle cx="40" cy="40" r={r} fill="none" strokeWidth="7" className="stroke-muted" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          strokeWidth="7"
          strokeLinecap="round"
          className="stroke-primary [filter:drop-shadow(0_0_5px_hsl(var(--primary)/0.55))] [transition:stroke-dashoffset_0.7s_cubic-bezier(0.16,1,0.3,1)]"
          strokeDasharray={c}
          strokeDashoffset={off}
        />
      </svg>
      <span className="absolute font-display text-xl font-semibold tabular-nums">{clamped}</span>
    </div>
  );
}
