"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/context/session";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AuthCallbackPage() {
  const { session, loading } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    const timer = setTimeout(() => router.replace(session ? "/" : "/login"), 1200);
    return () => clearTimeout(timer);
  }, [loading, session, router]);

  return (
    <Card className="border-border/80 bg-card/70 p-8 text-center">
      {loading ? (
        <>
          <h2 className="font-display text-2xl font-semibold">Confirming…</h2>
          <Skeleton className="mx-auto mt-4 h-4 w-40" />
        </>
      ) : session ? (
        <>
          <h2 className="font-display text-2xl font-semibold">Email confirmed</h2>
          <p className="mt-2 text-sm text-muted-foreground">Signing you in…</p>
        </>
      ) : (
        <>
          <h2 className="font-display text-2xl font-semibold">Confirmed</h2>
          <p className="mt-2 text-sm text-muted-foreground">Taking you to sign in…</p>
        </>
      )}
    </Card>
  );
}
