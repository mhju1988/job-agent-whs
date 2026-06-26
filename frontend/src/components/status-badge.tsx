import { STATUS_META } from "@/lib/status";
import type { ApplicationStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const meta = STATUS_META[status] ?? { label: status, key: "new" };
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium"
      style={{
        color: `hsl(var(--status-${meta.key}))`,
        backgroundColor: `hsl(var(--status-${meta.key}) / 0.12)`,
        borderColor: `hsl(var(--status-${meta.key}) / 0.3)`,
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: `hsl(var(--status-${meta.key}))` }}
      />
      {meta.label}
    </span>
  );
}
