"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Users } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { AdminUser } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";

type PendingAction =
  | { kind: "ban"; user: AdminUser }
  | { kind: "unban"; user: AdminUser }
  | { kind: "promote"; user: AdminUser }
  | { kind: "demote"; user: AdminUser };

function UserApplicationsDialog({
  user,
  onOpenChange,
}: {
  user: AdminUser | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: apps, isLoading } = useQuery({
    queryKey: ["admin", "applications", user?.id],
    queryFn: () => api.getUserApplications(user!.id),
    enabled: user !== null,
  });

  return (
    <Dialog open={user !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Applications — {user?.email ?? user?.id}</DialogTitle>
          <DialogDescription>Read-only support view. This access is logged.</DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : !apps || apps.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No applications for this user.
          </p>
        ) : (
          <div className="max-h-80 space-y-2 overflow-y-auto">
            {apps.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-border/60 p-3 text-sm"
              >
                <span className="truncate">{a.job_title ?? "Untitled role"}</span>
                <Badge variant="secondary">{a.status}</Badge>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AdminUsersPage() {
  const qc = useQueryClient();
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [viewingUser, setViewingUser] = useState<AdminUser | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: api.getAdminUsers,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "users"] });

  const ban = useMutation({
    mutationFn: (id: string) => api.banUser(id),
    onSuccess: () => {
      toast.success("User banned");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Ban failed"),
  });

  const unban = useMutation({
    mutationFn: (id: string) => api.unbanUser(id),
    onSuccess: () => {
      toast.success("User unbanned");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Unban failed"),
  });

  const confirmEmail = useMutation({
    mutationFn: (id: string) => api.confirmUserEmail(id),
    onSuccess: () => {
      toast.success("Email confirmed");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Confirm failed"),
  });

  const setRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: "user" | "admin" }) =>
      api.setUserRole(id, role),
    onSuccess: () => {
      toast.success("Role updated");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Role update failed"),
  });

  const runPending = () => {
    if (!pending) return;
    const { kind, user } = pending;
    if (kind === "ban") ban.mutate(user.id);
    if (kind === "unban") unban.mutate(user.id);
    if (kind === "promote") setRole.mutate({ id: user.id, role: "admin" });
    if (kind === "demote") setRole.mutate({ id: user.id, role: "user" });
    setPending(null);
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Users" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!users || users.length === 0) {
    return (
      <div className="mx-auto max-w-5xl">
        <PageHeader eyebrow="Admin" title="Users" />
        <EmptyState icon={Users} title="No users yet" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Manage accounts: confirm email, ban/unban, promote or demote."
      />
      <div className="space-y-3">
        {users.map((u) => (
          <Card key={u.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium">{u.email ?? u.id}</span>
                {u.role === "admin" && (
                  <Badge variant="secondary" className="gap-1">
                    <ShieldCheck className="h-3 w-3" />
                    Admin
                  </Badge>
                )}
                {u.banned && <Badge variant="destructive">Banned</Badge>}
                {!u.email_confirmed && <Badge variant="outline">Unconfirmed</Badge>}
              </div>
              <p className="text-xs text-muted-foreground">
                Joined {new Date(u.created_at).toLocaleDateString()}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => setViewingUser(u)}>
                View applications
              </Button>
              {!u.email_confirmed && (
                <Button size="sm" variant="outline" onClick={() => confirmEmail.mutate(u.id)}>
                  Confirm email
                </Button>
              )}
              {u.banned ? (
                <Button size="sm" variant="outline" onClick={() => setPending({ kind: "unban", user: u })}>
                  Unban
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPending({ kind: "ban", user: u })}
                >
                  Ban
                </Button>
              )}
              {u.role === "admin" ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPending({ kind: "demote", user: u })}
                >
                  Demote
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPending({ kind: "promote", user: u })}
                >
                  Promote
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title={
          pending?.kind === "ban"
            ? "Ban this user?"
            : pending?.kind === "unban"
              ? "Unban this user?"
              : pending?.kind === "promote"
                ? "Promote to admin?"
                : "Demote to regular user?"
        }
        description={pending?.user.email ?? pending?.user.id ?? ""}
        confirmLabel="Confirm"
        destructive={pending?.kind === "ban" || pending?.kind === "demote"}
        onConfirm={runPending}
      />
      <UserApplicationsDialog
        user={viewingUser}
        onOpenChange={(open) => !open && setViewingUser(null)}
      />
    </div>
  );
}
