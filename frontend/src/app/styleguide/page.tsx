import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const STATUSES = [
  ["new", "New"],
  ["ready", "Ready to send"],
  ["applied", "Applied"],
  ["interview", "Interview"],
  ["offer", "Offer"],
  ["rejected", "Rejected"],
] as const;

function ScoreGauge({ score }: { score: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const off = c * (1 - score / 100);
  return (
    <div className="relative grid h-24 w-24 place-items-center">
      <svg viewBox="0 0 80 80" className="h-24 w-24 -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" strokeWidth="7" className="stroke-muted" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          strokeWidth="7"
          strokeLinecap="round"
          className="stroke-primary [filter:drop-shadow(0_0_5px_hsl(var(--primary)/0.55))]"
          strokeDasharray={c}
          strokeDashoffset={off}
        />
      </svg>
      <span className="absolute font-display text-2xl font-semibold tabular-nums">{score}</span>
    </div>
  );
}

function Chip({ tone, children }: { tone: "match" | "gap"; children: React.ReactNode }) {
  const cls =
    tone === "match"
      ? "bg-status-offer/15 text-status-offer border-status-offer/30"
      : "bg-status-interview/15 text-status-interview border-status-interview/30";
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {children}
    </span>
  );
}

export default function StyleguidePage() {
  return (
    <div className="relative mx-auto max-w-5xl px-6 py-16">
      <div
        aria-hidden
        className="grid-texture pointer-events-none fixed inset-x-0 top-0 -z-10 h-[480px]"
      />
      {/* wordmark */}
      <div className="animate-fade-up flex items-center gap-2">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary font-display text-lg font-bold text-primary-foreground">
          J
        </div>
        <span className="font-display text-xl font-semibold tracking-tight">Job Agent</span>
        <Badge variant="outline" className="ml-2 text-muted-foreground">design system</Badge>
      </div>

      {/* hero */}
      <h1
        className="animate-fade-up mt-12 font-display text-6xl font-semibold leading-[1.04] tracking-tight"
        style={{ animationDelay: "60ms" }}
      >
        Bold, modern,
        <br />
        <span className="text-primary">unmistakably yours.</span>
      </h1>
      <p
        className="animate-fade-up mt-5 max-w-lg text-lg text-muted-foreground"
        style={{ animationDelay: "120ms" }}
      >
        Ink canvas, electric-lime accent, editorial display type. Every surface in
        the command center is built from these tokens.
      </p>

      {/* KPI cards */}
      <div className="animate-fade-up mt-12 grid grid-cols-2 gap-4 sm:grid-cols-4" style={{ animationDelay: "180ms" }}>
        {[
          ["Jobs scouted", "128"],
          ["Matches", "31"],
          ["Applications", "9"],
          ["Follow-ups due", "2"],
        ].map(([label, value]) => (
          <Card key={label} className="card-interactive border-border/80 bg-card/70 p-5">
            <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className="mt-2 font-display text-4xl font-semibold tabular-nums">{value}</div>
          </Card>
        ))}
      </div>

      {/* featured match card */}
      <Card
        className="card-interactive animate-fade-up mt-6 flex items-center gap-6 border-border/80 bg-card/70 p-6"
        style={{ animationDelay: "240ms" }}
      >
        <ScoreGauge score={90} />
        <div className="flex-1">
          <div className="font-display text-xl font-semibold">Senior Python Developer</div>
          <div className="text-sm text-muted-foreground">ACONEXT Engineering GmbH · Berlin</div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Chip tone="match">Python</Chip>
            <Chip tone="match">SQL</Chip>
            <Chip tone="match">REST APIs</Chip>
            <Chip tone="gap">AWS</Chip>
            <Chip tone="gap">Kubernetes</Chip>
          </div>
        </div>
        <Button>Prepare application</Button>
      </Card>

      {/* status palette */}
      <h2 className="mt-14 font-display text-2xl font-semibold">Application lifecycle</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {STATUSES.map(([key, label]) => (
          <span
            key={key}
            className="rounded-full border px-3 py-1 text-sm font-medium"
            style={{
              color: `hsl(var(--status-${key}))`,
              backgroundColor: `hsl(var(--status-${key}) / 0.12)`,
              borderColor: `hsl(var(--status-${key}) / 0.3)`,
            }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* buttons */}
      <h2 className="mt-14 font-display text-2xl font-semibold">Buttons</h2>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Delete my data</Button>
        <Button variant="link">Learn more</Button>
      </div>

      {/* type scale */}
      <h2 className="mt-14 font-display text-2xl font-semibold">Type</h2>
      <div className="mt-4 space-y-1">
        <p className="font-display text-5xl font-semibold tracking-tight">Display / Bricolage Grotesque</p>
        <p className="text-lg">Body / Hanken Grotesk — clean, readable, neutral.</p>
        <p className="font-mono text-sm text-muted-foreground">mono / JetBrains Mono — 0123456789</p>
      </div>
    </div>
  );
}
