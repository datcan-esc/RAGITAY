export function InlineMeta({
  label,
  value,
  compact = false,
}: {
  label: string
  value: string
  compact?: boolean
}) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-2xl)] bg-muted ${
        compact ? "px-2 py-1" : "px-3 py-2"
      }`}
    >
      <span
        className={`uppercase tracking-[0.14em] text-muted-foreground ${
          compact ? "text-[10px]" : "text-xs"
        }`}
      >
        {label}
      </span>
      <span className={compact ? "text-[13px] font-medium text-foreground" : "font-medium text-foreground"}>
        {value}
      </span>
    </div>
  )
}
