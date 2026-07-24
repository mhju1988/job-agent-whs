"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useSession } from "@/context/session";
import { shouldRedirectFromAdmin } from "@/lib/role";
import { AppShell } from "@/components/app-shell";
import { RunProvider } from "@/components/run-drawer";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminGroupLayout({ children }: { children: React.ReactNode }) {
  const { isAdmin, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (shouldRedirectFromAdmin({ loading, isAdmin })) {
      toast.error("Admin access required");
      router.replace("/");
    }
  }, [loading, isAdmin, router]);

  if (loading || !isAdmin) {
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
