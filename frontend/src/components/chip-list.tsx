export function ChipList({
  items,
  tone,
}: {
  items: string[];
  tone: "match" | "gap";
}) {
  if (!items.length) return null;
  const key = tone === "match" ? "offer" : "interview";
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
          style={{
            color: `hsl(var(--status-${key}))`,
            backgroundColor: `hsl(var(--status-${key}) / 0.12)`,
            borderColor: `hsl(var(--status-${key}) / 0.3)`,
          }}
        >
          {item}
        </span>
      ))}
    </div>
  );
}
