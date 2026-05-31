import { ExternalLink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

import { InlineMeta } from "./inline-meta"
import { DetailSkeleton } from "./skeletons"
import type { DecisionDetail } from "./types"

export function DetailPanel({
  detail,
  detailError,
  detailPending,
}: {
  detail: DecisionDetail | null
  detailError: string
  detailPending: boolean
}) {
  return (
    <Card className="min-w-0 rounded-[24px] border-border bg-card shadow-sm lg:sticky lg:top-6 lg:h-[calc(100vh-4rem)]">
      <CardHeader className="p-5 pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Karar detayı</CardTitle>
            <CardDescription>
              Seçilen kararın tam metni ve temel künyesi.
            </CardDescription>
          </div>
          {detail?.source_url ? (
            <Button asChild variant="outline" size="sm">
              <a href={detail.source_url} target="_blank" rel="noreferrer">
                Kaynak
                <ExternalLink className="size-4" />
              </a>
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="flex h-full min-h-0 flex-col gap-4 p-5 pt-0">
        {detailPending ? (
          <DetailSkeleton />
        ) : detailError ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
            {detailError}
          </div>
        ) : detail ? (
          <>
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge className="rounded-full">{detail.daire}</Badge>
                {detail.outcome ? (
                  <Badge variant="secondary" className="rounded-full">
                    {detail.outcome}
                  </Badge>
                ) : null}
              </div>
              <h2 className="text-lg font-semibold leading-8 text-foreground">
                {detail.title}
              </h2>
              <div className="grid gap-2 sm:grid-cols-3">
                <InlineMeta label="Esas" value={detail.esas_no || "-"} />
                <InlineMeta label="Karar" value={detail.karar_no || "-"} />
                <InlineMeta label="Tarih" value={detail.karar_tarihi || "-"} />
              </div>
            </div>
            <Separator />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-muted/40">
              <div className="border-b border-border px-4 py-3">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  Tam Metin
                </p>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4">
                <pre className="max-w-full whitespace-pre-wrap break-words font-sans text-sm leading-7 text-foreground/85 [word-break:break-word]">
                  {detail.full_text}
                </pre>
              </div>
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            Listeden bir karar seçtiğinizde tam metin burada açılacak.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
