import { cn } from "@/lib/utils";

/**
 * Reusable decorative background: three soft, slowly drifting gradient blobs in
 * the product palette (electric-lime / cyan / violet) over the dark canvas.
 *
 * - Pure CSS animation (no JS loop) → cheap and battery-friendly.
 * - `position: fixed`, behind all content (`z-index: -10`), `pointer-events: none`
 *   so it never intercepts clicks, scroll, or focus.
 * - Honours `prefers-reduced-motion` (blobs freeze in place — see globals.css).
 * - `aria-hidden` because it is purely decorative.
 *
 * Customisation knobs live on the `.animated-bg` class in globals.css
 * (`--blob-opacity`, `--blob-blur`, `--blob-speed-1..3`). Override per usage by
 * passing inline style via `className` (e.g. a wrapper that sets the CSS vars).
 */
export function AnimatedBackground({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("animated-bg", className)}>
      <span className="animated-bg__blob animated-bg__blob--1" />
      <span className="animated-bg__blob animated-bg__blob--2" />
      <span className="animated-bg__blob animated-bg__blob--3" />
    </div>
  );
}
