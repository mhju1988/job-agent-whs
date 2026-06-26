export function formatDuration(startedAt: string, finishedAt: string): string {
  const secs = Math.round(
    (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000,
  );
  if (isNaN(secs)) return "—";
  return secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function formatCost(eur: number | null | undefined): string {
  if (eur == null) return "—";
  if (eur === 0) return "€0.00";
  if (eur < 0.001) return "< €0.001";
  return `€${eur.toFixed(4)}`;
}
