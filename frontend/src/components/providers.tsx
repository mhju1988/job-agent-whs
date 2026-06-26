"use client";

import { useState } from "react";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { Toaster } from "@/components/ui/sonner";
import { SessionProvider } from "@/context/session";

/** App-wide client providers: data cache + auth session + toasts. */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error) => {
            const msg =
              error instanceof ApiError
                ? `${error.message} (${error.status})`
                : "Could not reach the API — is it running and are you signed in?";
            toast.error(msg);
          },
        }),
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <SessionProvider>{children}</SessionProvider>
      </MotionConfig>
      <Toaster richColors position="top-right" theme="dark" />
    </QueryClientProvider>
  );
}
