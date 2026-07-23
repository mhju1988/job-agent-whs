"use client";

import { Button } from "@/components/ui/button";

export function BulkActionBar({
  count,
  actionLabel,
  onAction,
  onSelectAll,
  onCancel,
  disabled,
  destructive,
}: {
  count: number;
  actionLabel: string;
  onAction: () => void;
  onSelectAll?: () => void;
  onCancel: () => void;
  disabled?: boolean;
  destructive?: boolean;
}) {
  return (
    <div className="sticky bottom-4 z-20 mx-auto flex w-fit items-center gap-3 rounded-full border border-border/80 bg-card/95 px-4 py-2 shadow-lg backdrop-blur">
      <span className="text-sm tabular-nums text-muted-foreground">
        {count} selected
      </span>
      {onSelectAll && (
        <Button variant="ghost" size="sm" onClick={onSelectAll}>
          Select all
        </Button>
      )}
      <Button
        size="sm"
        variant={destructive ? "destructive" : "default"}
        onClick={onAction}
        disabled={disabled || count === 0}
      >
        {actionLabel}
      </Button>
      <Button variant="ghost" size="sm" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}
