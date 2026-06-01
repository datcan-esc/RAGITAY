import { Badge } from "@/components/ui/badge"

export function ActiveFilters({
  sourceLabels,
  daire,
  yearFrom,
  yearTo,
  topDecisions,
}: {
  sourceLabels: string[]
  daire: string
  yearFrom: string
  yearTo: string
  topDecisions: string
}) {
  const items: string[] = []

  if (sourceLabels.length) {
    items.push(sourceLabels.join(" + "))
  }
  if (daire.trim()) {
    items.push(daire.trim())
  }
  if (yearFrom || yearTo) {
    items.push(`${yearFrom || "?"} - ${yearTo || "?"}`)
  }
  if (topDecisions) {
    items.push(`${topDecisions} karar`)
  }

  if (!items.length) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Badge key={item} variant="outline" className="rounded-full">
          {item}
        </Badge>
      ))}
    </div>
  )
}
