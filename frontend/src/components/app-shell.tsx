"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Briefcase,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Search,
  ShieldCheck,
  Send,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { useSession } from "@/context/session";
import { NextActionBanner } from "@/components/next-action-banner";
import { CommandPalette, OPEN_COMMAND_PALETTE } from "@/components/command-palette";

const NAV_GROUPS: { title?: string; items: { href: string; label: string; icon: typeof Briefcase }[] }[] = [
  { items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard }] },
  {
    title: "Workflow",
    items: [
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/matches", label: "Matches", icon: Sparkles },
      { href: "/graph", label: "Fit Graph", icon: Network },
      { href: "/applications", label: "Applications", icon: Send },
    ],
  },
  {
    title: "You",
    items: [{ href: "/profile", label: "Profile", icon: UserRound }],
  },
];

function navLinkClass(active: boolean) {
  return cn(
    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    active
      ? "bg-primary/10 text-primary"
      : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { isAdmin } = useSession();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);
  const groups = isAdmin
    ? [
        ...NAV_GROUPS,
        { title: "Admin", items: [{ href: "/admin", label: "Admin", icon: ShieldCheck }] },
      ]
    : NAV_GROUPS;
  return (
    <nav className="flex flex-1 flex-col gap-4">
      {groups.map((group, gi) => (
        <div key={group.title ?? `group-${gi}`} className="flex flex-col gap-1">
          {group.title && (
            <span className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
              {group.title}
            </span>
          )}
          {group.items.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={isActive(href) ? "page" : undefined}
              className={navLinkClass(isActive(href))}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}

/** Observability is a diagnostic tool, not a workflow step — kept small and low. */
function ActivityLink({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = pathname.startsWith("/observability");
  return (
    <Link
      href="/observability"
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors",
        active
          ? "text-primary"
          : "text-muted-foreground/70 hover:bg-accent hover:text-foreground",
      )}
    >
      <Activity className="h-3.5 w-3.5" />
      Activity
    </Link>
  );
}

function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary font-display text-base font-bold text-primary-foreground">
        J
      </div>
      <span className="font-display text-lg font-semibold tracking-tight">Job Agent</span>
    </Link>
  );
}

function UserMenu() {
  const { user, signOut } = useSession();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-accent">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-secondary text-xs font-semibold uppercase">
            {user?.email?.[0] ?? "?"}
          </div>
          <span className="truncate text-muted-foreground">{user?.email}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void signOut()} className="cursor-pointer">
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-dvh">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-border bg-card/40 p-4 md:flex">
        <div className="mb-8 px-2">
          <Wordmark />
        </div>
        <NavLinks />
        <div className="mt-2 border-t border-border/60 pt-2">
          <ActivityLink />
        </div>
        <UserMenu />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-border bg-background/80 px-4 py-3 backdrop-blur sm:px-6">
          {/* Mobile nav trigger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="flex w-64 flex-col border-border bg-card p-4">
              <SheetTitle className="mb-6">
                <Wordmark />
              </SheetTitle>
              <NavLinks onNavigate={() => setMobileOpen(false)} />
              <div className="mt-2 border-t border-border/60 pt-2">
                <ActivityLink onNavigate={() => setMobileOpen(false)} />
              </div>
              <UserMenu />
            </SheetContent>
          </Sheet>

          <span className="font-display text-base font-semibold md:hidden">Job Agent</span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE))}
            aria-label="Open command menu"
            className="flex items-center gap-2 rounded-lg border border-border/70 bg-card/50 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <Search className="h-4 w-4" />
            <span className="hidden sm:inline">Search or run…</span>
            <kbd className="hidden rounded border border-border bg-muted px-1.5 font-mono text-[10px] leading-5 sm:inline">
              ⌘K
            </kbd>
          </button>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <NextActionBanner />
          {children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
