"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { runStream } from "@/lib/sse";
import { showRunResultToast } from "@/lib/run-result-toast";
import { runInvalidationKeys } from "@/lib/run-invalidation";
import type { ProgressEvent, RunKind } from "@/lib/types";

type RunStatus = "idle" | "running" | "done" | "error" | "cancelled";

interface RunContextValue {
  start: (kind: RunKind, body?: Record<string, unknown>, label?: string) => void;
  status: RunStatus;
}

const RunContext = createContext<RunContextValue | undefined>(undefined);

function stageLabel(e: ProgressEvent): string {
  switch (e.stage) {
    case "suggesting":
      return e.keyword
        ? `Chose role from your CV: ${String(e.keyword)}`
        : "Choosing the best roles from your CV…";
    case "start":
      return e.total != null ? `Starting (${e.total} steps)…` : "Starting…";
    case "source":
      return `Scouting ${e.source} (${e.current}/${e.total})`;
    case "scoring":
      return `Scoring matches (${e.current}/${e.total})`;
    case "loading":
      return "Loading profile + job…";
    case "rendering":
      return "Writing the cover letter…";
    case "exporting":
      return "Exporting documents…";
    case "persisting":
      return "Saving the application…";
    case "done":
      return "Done.";
    default:
      return e.stage;
  }
}

export function RunProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [title, setTitle] = useState("Agent run");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const kindRef = useRef<RunKind | null>(null);

  const start = useCallback(
    (kind: RunKind, body: Record<string, unknown> = {}, label = "Agent run") => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      kindRef.current = kind;
      setTitle(label);
      setEvents([]);
      setErrorMsg(null);
      setStatus("running");
      setOpen(true);
      void runStream(
        kind,
        body,
        {
          onProgress: (e) => {
            if (ctrl.signal.aborted) return;
            setEvents((prev) => [...prev, e]);
          },
          onResult: (result) => {
            if (ctrl.signal.aborted) return;
            setStatus("done");
            for (const key of runInvalidationKeys(kind)) {
              qc.invalidateQueries({ queryKey: key });
            }
            showRunResultToast(kind, result, (href) => router.push(href));
          },
          onError: (msg) => {
            if (ctrl.signal.aborted) return; // a superseded run was aborted — ignore
            setErrorMsg(msg);
            setStatus("error");
            toast.error(msg);
          },
        },
        ctrl.signal,
      );
    },
    [qc, router],
  );

  const cancel = useCallback(() => {
    // Abort the connection -> backend's generator finally sets the stop event
    // -> the worker thread breaks at its next loop boundary. The post-abort
    // onResult early-returns, so fire the run's invalidation here instead so
    // partial results surface.
    abortRef.current?.abort();
    setStatus("cancelled");
    const kind = kindRef.current;
    if (kind) {
      for (const key of runInvalidationKeys(kind)) {
        qc.invalidateQueries({ queryKey: key });
      }
    }
  }, [qc]);

  return (
    <RunContext.Provider value={{ start, status }}>
      {children}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex w-full flex-col gap-0 border-border bg-card sm:max-w-md">
          <SheetHeader className="border-b border-border pb-4 text-left">
            <SheetTitle className="flex items-center gap-2 font-display text-lg font-semibold">
              <span
                className={`h-2 w-2 rounded-full ${
                  status === "running"
                    ? "animate-pulse bg-primary"
                    : status === "error"
                      ? "bg-status-rejected"
                      : status === "cancelled"
                        ? "bg-muted-foreground"
                        : "bg-status-offer"
                }`}
              />
              {title}
            </SheetTitle>
            <p className="text-sm text-muted-foreground">
              {status === "running"
                ? "Streaming live progress…"
                : status === "error"
                  ? (errorMsg ?? "The run hit an error.")
                  : status === "cancelled"
                    ? "Cancelled — partial results saved."
                    : "Run complete."}
            </p>
            {status === "running" && (
              <button
                type="button"
                onClick={cancel}
                className="mt-2 self-start rounded-md border border-border px-3 py-1 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Cancel run
              </button>
            )}
          </SheetHeader>
          <ol className="flex-1 space-y-2 overflow-y-auto py-4 font-mono text-sm">
            <AnimatePresence initial={false}>
              {events.map((e, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.18, ease: "easeOut" }}
                  className="flex items-center gap-2 text-muted-foreground"
                >
                  <span className="text-primary">›</span>
                  {stageLabel(e)}
                </motion.li>
              ))}
            </AnimatePresence>
            {status === "running" && (
              <li className="flex items-center gap-2 text-primary">
                <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
                working…
              </li>
            )}
          </ol>
        </SheetContent>
      </Sheet>
    </RunContext.Provider>
  );
}

export function useRun(): RunContextValue {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used within RunProvider");
  return ctx;
}
