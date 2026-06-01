import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { ResultListSkeleton } from "./skeletons"
import type { SearchResult } from "./types"
import { formatSectionName } from "./utils"

export function ResultsList({
  isPending,
  results,
  activeDecisionId,
  onSelect,
}: {
  isPending: boolean
  results: SearchResult[]
  activeDecisionId: number | null
  onSelect: (decisionId: number) => void
}) {
  if (isPending) {
    return (
      <>
        <ResultListSkeleton />
        <ResultListSkeleton />
        <ResultListSkeleton />
      </>
    )
  }

  if (!results.length) {
    return (
      <Card className="rounded-[var(--radius-3xl)] border-dashed border-border bg-card">
        <CardContent className="p-8 text-center text-sm text-muted-foreground">
          Henüz sonuç yok. Arama yaptığınızda karar listesi burada oluşacak.
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      {results.map((result) => (
        <button
          key={`${result.source_name}-${result.external_id}`}
          type="button"
          onClick={() => onSelect(result.decision_id)}
          className={cn(
            "w-full rounded-[var(--radius-2xl)] border bg-card p-5 text-left transition shadow-sm hover:-translate-y-0.5 hover:border-border hover:bg-surface hover:shadow-md",
            activeDecisionId === result.decision_id
              ? "border-primary bg-accent shadow-md ring-1 ring-border"
              : "border-border"
          )}
        >
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                {result.outcome ? (
                  <Badge variant="secondary" className="rounded-full">
                    {result.outcome}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="rounded-full">
                    Karar
                  </Badge>
                )}
                <span className="text-sm text-muted-foreground">
                  {result.karar_tarihi || "-"}
                </span>
                </div>
                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  {formatSectionName(result.passages[0]?.section_name || "metin")}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-xs font-medium text-muted-foreground">
                  %{(result.score * 100).toFixed(1)}
                </p>
              </div>
            </div>
            <h3 className="text-base font-semibold leading-7 text-foreground">
              {result.title}
            </h3>
            <p className="line-clamp-3 text-sm leading-7 text-foreground">
              {result.passages[0]?.chunk_text ||
                "Bu karar için öne çıkan pasaj bulunamadı."}
            </p>
          </div>
        </button>
      ))}
    </>
  )
}
