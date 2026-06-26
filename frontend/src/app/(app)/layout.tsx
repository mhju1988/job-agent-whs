"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/context/session";
import { AppShell } from "@/components/app-shell";
import { RunProvider } from "@/components/run-drawer";
import { Skeleton } from "@/components/ui/skeleton";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const { session, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-3">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  return (
    <RunProvider>
      <AppShell>{children}</AppShell>
    </RunProvider>
  );
}
