/** Single source of truth for the fit-graph palette. Built on the shared
 *  `scoreBand` thresholds so the graph matches the rest of the app, and on
 *  design tokens so there is no scattered hex. */
import { type Band, scoreBand } from "./match-bands";

export const BAND_COLOR: Record<Band, string> = {
  strong: "hsl(var(--status-offer))",
  good: "#eab308", // yellow-500, matching the Matches page bands
  weak: "hsl(var(--status-rejected))",
};

export const GRAPH_COLOR = {
  accent: "hsl(var(--primary))", // the CV / electric-lime
  axis: "hsl(var(--border))",
  muted: "hsl(var(--muted-foreground))",
  text: "hsl(var(--foreground))",
} as const;

/** Band a 0..100 fit value (LLM score, or cosine·100). */
export function fitBand(fit: number): Band {
  return scoreBand(fit);
}

/** Token color for a 0..100 fit value. */
export function fitColor(fit: number): string {
  return BAND_COLOR[fitBand(fit)];
}
