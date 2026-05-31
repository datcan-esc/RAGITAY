import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

import { InlineMeta } from "./inline-meta"
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
      <Card className="rounded-[24px] border-dashed border-border bg-card">
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
            "w-full rounded-[22px] border bg-card p-5 text-left transition shadow-sm",
            activeDecisionId === result.decision_id
              ? "border-primary"
              : "border-border hover:border-foreground/20"
          )}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                <Badge className="rounded-full">{result.daire}</Badge>
                {result.outcome ? (
                  <Badge variant="secondary" className="rounded-full">
                    {result.outcome}
                  </Badge>
                ) : null}
              </div>
              <h3 className="text-base font-semibold leading-7 text-foreground">
                {result.title}
              </h3>
              <p className="text-sm text-muted-foreground">
                {result.mahkeme || "Mahkeme bilgisi bulunamadı"}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                Skor
              </p>
              <p className="mt-1 text-lg font-semibold text-foreground">
                {(result.score * 100).toFixed(1)}
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-sm text-slate-600">
            <InlineMeta label="Esas" value={result.esas_no || "-"} />
            <InlineMeta label="Karar" value={result.karar_no || "-"} />
            <InlineMeta label="Tarih" value={result.karar_tarihi || "-"} />
          </div>

          <p className="mt-4 line-clamp-3 text-sm leading-7 text-foreground/85">
            {result.passages[0]?.chunk_text ||
              "Bu karar için öne çıkan pasaj bulunamadı."}
          </p>

          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Detay görüntüle
            </span>
            <span className="text-sm text-muted-foreground">
              {formatSectionName(result.passages[0]?.section_name || "metin")}
            </span>
          </div>
        </button>
      ))}
    </>
  )
}
