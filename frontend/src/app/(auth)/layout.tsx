import { LoginHero } from "@/components/login-hero";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-card/40 p-12 lg:flex">
        <div className="grid-texture pointer-events-none absolute inset-0 -z-20 opacity-50" />
        {/* Matching constellation — the project idea in 3D */}
        <div className="pointer-events-none absolute inset-0 -z-10">
          <LoginHero />
        </div>
        {/* Scrim so the headline stays legible over the scene */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-2/3 bg-gradient-to-t from-card via-card/70 to-transparent" />

        <div className="relative flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary font-display text-lg font-bold text-primary-foreground">
            J
          </div>
          <span className="font-display text-xl font-semibold tracking-tight">Job Agent</span>
        </div>
        <div className="relative">
          <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight">
            Matched to the
            <br />
            <span className="text-primary">right opportunities.</span>
          </h1>
          <p className="mt-5 max-w-md text-lg text-muted-foreground">
            Scout listings, match them to your CV, draft tailored letters, and track
            every application — you keep the final click.
          </p>
        </div>
        <p className="relative text-sm text-muted-foreground">W-HS · Agentic AI</p>
      </div>
      {/* Form panel */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
