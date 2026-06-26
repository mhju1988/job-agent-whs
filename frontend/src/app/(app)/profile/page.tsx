"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Check, FileUp, Loader2, Pencil, Plus, ShieldAlert, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { uploadCvStream } from "@/lib/sse";
import type { CvUploadResult, ProgressEvent } from "@/lib/types";
import { useSession } from "@/context/session";
import { profileCompleteness } from "@/lib/profile-completeness";
import { normalizeSkills } from "@/lib/profile-skills";
import { validateCvFile } from "@/lib/cv-file";
import { PageHeader } from "@/components/page-header";
import { ChipList } from "@/components/chip-list";
import { ProfileTimeline } from "@/components/profile-timeline";
import { useRun } from "@/components/run-drawer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const STEPS = [
  { key: "parsing", label: "Reading & parsing your CV" },
  { key: "embedding", label: "Generating embeddings" },
  { key: "saving", label: "Saving your profile" },
  { key: "rescoring", label: "Re-scoring job matches" },
] as const;

// Derive the core index mapping from STEPS so adding/reordering steps
// auto-updates indices without touching this object.
const STAGE_TO_STEP: Record<string, number> = {
  ...Object.fromEntries(STEPS.map((s, i) => [s.key, i])),
  // Matcher-internal stages forwarded through profile_service.on_progress;
  // all pin to the final "rescoring" step.
  start: STEPS.length - 1,
  scoring: STEPS.length - 1,
  done: STEPS.length - 1,
};

export default function ProfilePage() {
  const qc = useQueryClient();
  const { signOut } = useSession();
  const fileRef = useRef<HTMLInputElement>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [scoreDetail, setScoreDetail] = useState("");
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const uploadAbortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight upload on unmount (navigate-away).
  useEffect(() => {
    return () => { uploadAbortRef.current?.abort(); };
  }, []);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: api.getProfile,
  });

  const run = useRun();
  const { data: matches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.getMatches(0),
  });

  const [editing, setEditing] = useState(false);
  const [draftSkills, setDraftSkills] = useState<string[]>([]);
  const [draftSummary, setDraftSummary] = useState("");
  const [skillInput, setSkillInput] = useState("");
  const [rescoreOpen, setRescoreOpen] = useState(false);
  const [rescoreK, setRescoreK] = useState(1);

  function startEdit() {
    setDraftSkills(profile?.skills ?? []);
    setDraftSummary(profile?.summary ?? "");
    setSkillInput("");
    setEditing(true);
  }
  function addSkill() {
    setDraftSkills((prev) => normalizeSkills([...prev, skillInput]));
    setSkillInput("");
  }
  function removeSkill(s: string) {
    setDraftSkills((prev) => prev.filter((x) => x !== s));
  }

  const update = useMutation({
    mutationFn: () =>
      api.updateProfile({
        skills: normalizeSkills([...draftSkills, skillInput]),
        summary: draftSummary,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      setEditing(false);
      toast.success("Profile updated", {
        description:
          matches.length > 0
            ? "Re-score your matches to apply the change?"
            : "Embeddings updated.",
        ...(matches.length > 0 && {
          action: {
            label: "Re-score",
            onClick: () => {
              setRescoreK(Math.min(25, matches.length));
              setRescoreOpen(true);
            },
          },
        }),
      });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Update failed"),
  });

  function handleFile(file: File) {
    const check = validateCvFile(file);
    if (!check.ok) {
      toast.error(check.error);
      return;
    }

    uploadAbortRef.current?.abort(); // cancel any previous upload
    const ctrl = new AbortController();
    uploadAbortRef.current = ctrl;

    setUploading(true);
    setStepIdx(0);
    setScoreDetail("");

    // uploadCvStream always resolves (errors delivered via onError), but we
    // add a .catch() as a defense against truly unexpected rejections so the
    // button is never left permanently disabled.
    uploadCvStream(
      file,
      {
        onProgress: (e: ProgressEvent) => {
          const idx = STAGE_TO_STEP[e.stage];
          if (idx != null) setStepIdx(idx);
          if (e.stage === "scoring" && e.total)
            setScoreDetail(`${e.current}/${e.total}`);
        },
        onResult: (raw) => {
          uploadAbortRef.current = null;
          const res = raw as unknown as CvUploadResult;
          setUploading(false);
          if (res.ok === false) {
            toast.error(res.error ?? "Upload failed");
            return;
          }
          toast.success(
            res.rescored != null
              ? `Profile updated — ${res.rescored} jobs re-scored.`
              : "Profile updated.",
          );
          qc.invalidateQueries({ queryKey: ["profile"] });
          qc.invalidateQueries({ queryKey: ["me"] });
          qc.invalidateQueries({ queryKey: ["matches"] });
          qc.invalidateQueries({ queryKey: ["search-suggestions"] });
        },
        onError: (msg) => {
          uploadAbortRef.current = null;
          setUploading(false);
          toast.error(msg);
        },
      },
      ctrl.signal,
    ).catch(() => {
      // Defense-in-depth: uploadCvStream handles all errors internally, but
      // if it ever rejects unexpectedly, reset the UI rather than leaving the
      // button disabled.
      if (!ctrl.signal.aborted) setUploading(false);
    });
  }

  const wipe = useMutation({
    mutationFn: () => api.deleteMyData(),
    onSuccess: async (s) => {
      toast.success(
        `Deleted ${s.profiles_deleted} profile, ${s.matches_deleted} matches, ${s.applications_deleted} applications.`,
      );
      setConfirmOpen(false);
      await signOut();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Delete failed"),
  });

  const skills = profile?.skills ?? [];

  // Page-level drag-and-drop. Depth counter avoids flicker as the drag passes
  // over child elements (each fires its own enter/leave).
  function onDragEnter(e: DragEvent) {
    if (uploading || !e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  }
  function onDragLeave(e: DragEvent) {
    if (!dragging) return;
    e.preventDefault();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setDragging(false);
    }
  }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (uploading) return;
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }

  return (
    <div
      className="relative mx-auto max-w-3xl"
      onDragEnter={onDragEnter}
      onDragOver={(e) => {
        if (dragging) e.preventDefault();
      }}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Drag overlay */}
      <AnimatePresence>
        {dragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute inset-0 z-20 grid place-items-center rounded-2xl border-2 border-dashed border-primary bg-background/80 backdrop-blur-sm"
          >
            <div className="flex flex-col items-center gap-2 text-primary">
              <UploadCloud className="h-8 w-8" />
              <span className="font-display font-semibold">Drop your CV to upload</span>
              <span className="text-xs text-muted-foreground">PDF, up to 10 MB</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <PageHeader
        eyebrow="You"
        title="Profile"
        description="Your CV powers matching and document generation."
        actions={
          <>
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
                e.target.value = "";
              }}
            />
            <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
              <FileUp className="mr-2 h-4 w-4" />
              {uploading ? "Uploading…" : "Upload CV (PDF)"}
            </Button>
          </>
        }
      />

      {/* Live upload progress */}
      <AnimatePresence>
        {uploading && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden"
          >
            <Card className="border-primary/30 bg-card/70 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="font-display font-semibold">Processing your CV…</span>
              </div>
              <ol className="space-y-3">
                {STEPS.map((step, i) => {
                  const done = i < stepIdx;
                  const active = i === stepIdx;
                  return (
                    <li key={step.key} className="flex items-center gap-3 text-sm">
                      <span
                        className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${
                          done
                            ? "border-status-offer bg-status-offer/15 text-status-offer"
                            : active
                              ? "border-primary text-primary"
                              : "border-border text-muted-foreground"
                        }`}
                      >
                        {done ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : active ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <span className="h-1.5 w-1.5 rounded-full bg-current opacity-40" />
                        )}
                      </span>
                      <span className={done || active ? "text-foreground" : "text-muted-foreground"}>
                        {step.label}
                        {active && step.key === "rescoring" && scoreDetail && (
                          <span className="ml-1 font-mono text-xs text-muted-foreground">
                            ({scoreDetail})
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : profile && Object.keys(profile).length > 0 ? (
        <Card className="space-y-5 border-border/80 bg-card/70 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Name</div>
              <div className="mt-1 font-display text-2xl font-semibold">
                {profile.full_name ?? "Unnamed"}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {!editing && (
                <Button variant="outline" size="sm" onClick={startEdit}>
                  <Pencil className="mr-2 h-3.5 w-3.5" />
                  Edit
                </Button>
              )}
              {(() => {
                const c = profileCompleteness(profile);
                return (
                  <div className="w-40 shrink-0">
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Profile</span>
                      <span className="font-semibold tabular-nums">{c.percent}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${c.percent}%` }}
                      />
                    </div>
                    {c.missing.length > 0 && (
                      <p className="mt-1 text-[11px] leading-snug text-muted-foreground/80">
                        Add: {c.missing.join(", ")}
                      </p>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>

          {/* Summary */}
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Summary</div>
            {editing ? (
              <textarea
                value={draftSummary}
                onChange={(e) => setDraftSummary(e.target.value)}
                rows={4}
                maxLength={5000}
                placeholder="A short professional summary…"
                className="mt-1 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            ) : profile.summary ? (
              <p className="mt-1 text-sm text-muted-foreground">{profile.summary}</p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground/60">No summary yet.</p>
            )}
          </div>

          {/* Skills */}
          <div>
            <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
              Skills ({editing ? draftSkills.length : skills.length})
            </div>
            {editing ? (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  {draftSkills.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs"
                    >
                      {s}
                      <button
                        type="button"
                        onClick={() => removeSkill(s)}
                        aria-label={`Remove ${s}`}
                        className="text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {draftSkills.length === 0 && (
                    <span className="text-xs text-muted-foreground/60">
                      No skills — add some below.
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <Input
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === ",") {
                        e.preventDefault();
                        addSkill();
                      }
                    }}
                    placeholder="Add a skill and press Enter"
                    className="h-9"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addSkill}
                    disabled={!skillInput.trim()}
                    aria-label="Add skill"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : skills.length > 0 ? (
              <ChipList items={skills} tone="match" />
            ) : (
              <p className="text-sm text-muted-foreground/60">No skills yet.</p>
            )}
          </div>

          {!editing && ((profile.experience?.length ?? 0) > 0 ||
            (profile.education?.length ?? 0) > 0) && (
            <ProfileTimeline
              experience={profile.experience ?? []}
              education={profile.education ?? []}
            />
          )}
          {!editing && (profile.languages?.length ?? 0) > 0 && (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                Languages
              </div>
              <ChipList items={profile.languages ?? []} tone="match" />
            </div>
          )}

          {editing && (
            <div className="flex justify-end gap-2 border-t border-border/60 pt-4">
              <Button
                variant="ghost"
                onClick={() => setEditing(false)}
                disabled={update.isPending}
              >
                Cancel
              </Button>
              <Button onClick={() => update.mutate()} disabled={update.isPending}>
                {update.isPending ? "Saving…" : "Save changes"}
              </Button>
            </div>
          )}
        </Card>
      ) : (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="group flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-border bg-card/40 p-12 text-center transition-colors hover:border-primary/60 hover:bg-primary/5 disabled:opacity-50"
        >
          <span className="grid h-14 w-14 place-items-center rounded-full bg-primary/10 text-primary transition-transform group-hover:scale-105">
            <UploadCloud className="h-7 w-7" />
          </span>
          <span className="font-display text-lg font-semibold text-foreground">
            Upload your CV to get started
          </span>
          <span className="max-w-sm text-sm text-muted-foreground">
            Drag &amp; drop a PDF here, or click to browse. We&apos;ll parse it into a
            profile and start matching jobs automatically.
          </span>
        </button>
      )}

      {/* Danger zone */}
      <div className="mt-10 rounded-xl border border-destructive/30 bg-destructive/5 p-6">
        <div className="flex items-center gap-2 text-destructive">
          <ShieldAlert className="h-5 w-5" />
          <h2 className="font-display text-lg font-semibold">Danger zone</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Permanently delete your profile, match scores, applications, and generated
          documents (GDPR right to erasure). You will be signed out.
        </p>
        <Dialog open={rescoreOpen} onOpenChange={setRescoreOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Re-score matches</DialogTitle>
              <DialogDescription>
                Re-score your top {rescoreK} of {matches.length}{" "}
                {matches.length === 1 ? "match" : "matches"}? Each is one LLM call.
              </DialogDescription>
            </DialogHeader>
            <Input
              type="number"
              min={1}
              max={matches.length}
              value={rescoreK}
              onChange={(e) =>
                setRescoreK(
                  Math.max(1, Math.min(matches.length, Number(e.target.value) || 1)),
                )
              }
              aria-label="How many matches to re-score"
            />
            <DialogFooter>
              <Button variant="ghost" onClick={() => setRescoreOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  run.start(
                    "rescore",
                    { limit: rescoreK },
                    `Re-scoring top ${rescoreK} matches`,
                  );
                  setRescoreOpen(false);
                }}
              >
                Re-score top {rescoreK}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive" className="mt-4">
              Delete my data
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete everything?</DialogTitle>
              <DialogDescription>
                This cannot be undone. All your data is removed from the system.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={wipe.isPending}
                onClick={() => wipe.mutate()}
              >
                {wipe.isPending ? "Deleting…" : "Yes, delete everything"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
