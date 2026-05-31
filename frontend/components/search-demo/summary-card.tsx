import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

import type { SummaryResponse } from "./types"

export function SummaryCard({
  isPending,
  summary,
  resultCount,
}: {
  isPending: boolean
  summary: SummaryResponse | null
  resultCount: number
}) {
  return (
    <Card className="rounded-[24px] border-border bg-card shadow-sm">
      <CardHeader className="p-5 pb-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Kısa özet</CardTitle>
            <CardDescription>Bulunan kararların kısa çalışma özeti.</CardDescription>
          </div>
          <Badge variant="outline" className="rounded-full">
            {resultCount ? `${resultCount} sonuç` : "Demo"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-5 pt-0">
        {isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-14 rounded-2xl" />
            <Skeleton className="h-14 rounded-2xl" />
            <Skeleton className="h-24 rounded-2xl" />
          </div>
        ) : summary ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="rounded-full">
                {summary.provider}
              </Badge>
              <Badge variant="outline" className="rounded-full">
                {summary.model}
              </Badge>
              {summary.fallback_used ? (
                <Badge variant="outline" className="rounded-full">
                  fallback
                </Badge>
              ) : null}
            </div>
            <div className="rounded-2xl border border-border bg-muted/50 p-4">
              <p className="text-sm leading-7 text-foreground/85">
                {summary.general_summary}
              </p>
            </div>

            {summary.key_points.length ? (
              <div className="rounded-2xl border border-border bg-muted/30 p-4">
                <p className="mb-3 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Öne çıkan noktalar
                </p>
                <div className="space-y-2">
                  {summary.key_points.map((item) => (
                    <div key={item} className="flex items-start gap-2">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-foreground/70" />
                      <p className="text-sm leading-7 text-foreground/85">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {summary.decision_summaries.slice(0, 3).map((item) => (
              <div
                key={`${item.decision_id}-${item.reference}`}
                className="rounded-2xl border border-border bg-muted/50 p-4"
              >
                <p className="text-sm leading-7 text-foreground/85">
                  {item.short_summary}
                </p>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  {item.why_relevant}
                </p>
                <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {item.reference}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Arama yapıldığında kısa özet burada görünecek.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
