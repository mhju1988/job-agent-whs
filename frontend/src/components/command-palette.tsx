"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  Activity,
  Briefcase,
  LayoutDashboard,
  Network,
  Search,
  Send,
  Sparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { useRun } from "@/components/run-drawer";

/** Fire this event (e.g. from a header button) to open the palette. */
export const OPEN_COMMAND_PALETTE = "command-palette:open";

function Item({
  icon: Icon,
  label,
  hint,
  onSelect,
}: {
  icon: LucideIcon;
  label: string;
  hint?: string;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm aria-selected:bg-accent aria-selected:text-foreground"
    >
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="flex-1">{label}</span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </Command.Item>
  );
}

const NAV: { icon: LucideIcon; label: string; href: string }[] = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: Briefcase, label: "Jobs", href: "/jobs" },
  { icon: Sparkles, label: "Matches", href: "/matches" },
  { icon: Network, label: "Fit Graph", href: "/graph" },
  { icon: Send, label: "Applications", href: "/applications" },
  { icon: UserRound, label: "Profile", href: "/profile" },
  { icon: Activity, label: "Activity", href: "/observability" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const run = useRun();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    const onOpen = () => setOpen(true);
    document.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_COMMAND_PALETTE, onOpen);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_COMMAND_PALETTE, onOpen);
    };
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };
  const act = (fn: () => void) => {
    setOpen(false);
    fn();
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command menu"
      overlayClassName="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm"
      contentClassName="fixed left-1/2 top-[16%] z-50 w-[92vw] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-popover shadow-2xl"
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <Command.Input
          placeholder="Search or run a command…"
          className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <Command.List className="max-h-80 overflow-y-auto p-2 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground/70">
        <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
          No matching commands.
        </Command.Empty>

        <Command.Group heading="Actions">
          <Item
            icon={Sparkles}
            label="Smart Find"
            hint="AI picks the best role"
            onSelect={() =>
              act(() =>
                run.start("scout-matcher", { max_results: 10 }, "Smart Find"),
              )
            }
          />
          <Item
            icon={Briefcase}
            label="Search jobs"
            onSelect={() => go("/jobs")}
          />
        </Command.Group>

        <Command.Group heading="Go to">
          {NAV.map((n) => (
            <Item
              key={n.href}
              icon={n.icon}
              label={n.label}
              onSelect={() => go(n.href)}
            />
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
