import Image from "next/image"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
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
    <Card className="rounded-[var(--radius-3xl)] border-border bg-card shadow-sm">
      <CardHeader className="p-5 pb-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Kısa özet</CardTitle>
          </div>
          <Badge variant="outline" className="rounded-full">
            {resultCount ? `${resultCount} sonuç` : "Demo"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-5 pt-0">
        {isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-14 rounded-[var(--radius-2xl)]" />
            <Skeleton className="h-14 rounded-[var(--radius-2xl)]" />
            <Skeleton className="h-24 rounded-[var(--radius-2xl)]" />
          </div>
        ) : summary ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="rounded-full">
                {summary.provider === "gemini" ? (
                  <Image
                    src="https://www.gstatic.com/lamda/images/gemini_sparkle_aurora_33f86dc0c0257da337c63.svg"
                    alt=""
                    width={14}
                    height={14}
                    className="size-3.5"
                  />
                ) : null}
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
            <div className="rounded-[var(--radius-2xl)] border border-border bg-muted p-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                AI değerlendirmesi
              </p>
              <p className="text-sm leading-7 text-foreground">
                {summary.general_summary}
              </p>
            </div>

            {summary.key_points.length ? (
              <div className="rounded-[var(--radius-2xl)] border border-border bg-muted p-4">
                <p className="mb-3 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Öne çıkan noktalar
                </p>
                <div className="space-y-2">
                  {summary.key_points.map((item) => (
                    <div key={item} className="flex items-start gap-2">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-foreground" />
                      <p className="text-sm leading-7 text-foreground">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
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
