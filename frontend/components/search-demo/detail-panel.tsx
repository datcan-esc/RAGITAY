import { useState } from "react"
import { Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"

import { DecisionChatPanel } from "./decision-chat-panel"
import { InlineMeta } from "./inline-meta"
import { DetailSkeleton } from "./skeletons"
import type {
  DecisionChatResponse,
  DecisionDetail,
  DecisionMiniSummary,
} from "./types"

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

function buildHighlightedHtml(text: string, terms: string[]) {
  const uniqueTerms = Array.from(
    new Set(
      terms
        .flatMap((term) => term.split(/\s+/))
        .map((term) => term.trim())
        .filter((term) => term.length >= 3)
    )
  )

  if (!uniqueTerms.length) {
    return escapeHtml(text)
  }

  const pattern = new RegExp(`(${uniqueTerms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi")
  return escapeHtml(text).replace(pattern, '<mark class="rounded bg-sidebar-primary px-0.5 text-sidebar">$1</mark>')
}

export function DetailPanel({
  detail,
  detailError,
  detailPending,
  decisionSummary,
  decisionSummaryPending,
  chatQuestion,
  chatAnswer,
  chatPending,
  chatError,
  onChatQuestionChange,
  onChatSubmit,
  onDecisionSummaryGenerate,
}: {
  detail: DecisionDetail | null
  detailError: string
  detailPending: boolean
  decisionSummary: DecisionMiniSummary | null
  decisionSummaryPending: boolean
  chatQuestion: string
  chatAnswer: DecisionChatResponse | null
  chatPending: boolean
  chatError: string
  onChatQuestionChange: (value: string) => void
  onChatSubmit: () => void
  onDecisionSummaryGenerate: () => void
}) {
  const [activeView, setActiveView] = useState<"text" | "ai">("text")
  const [documentSearch, setDocumentSearch] = useState("")

  const highlightedFullText = detail?.full_text
    ? buildHighlightedHtml(detail.full_text, [documentSearch])
    : ""

  return (
    <Card className="flex min-w-0 flex-col overflow-hidden rounded-[var(--radius-3xl)] border-border bg-card shadow-sm lg:sticky lg:top-6 lg:h-[calc(100vh-4rem)]">
      <CardHeader className="p-5 pb-3">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base">Karar detayı</CardTitle>
            {detail ? (
              <div className="inline-flex items-center gap-1 rounded-[var(--radius-2xl)] border border-border bg-muted p-1">
                <button
                  type="button"
                  onClick={() => setActiveView("text")}
                  className={`rounded-[var(--radius-xl)] px-3 py-1.5 text-xs font-medium transition ${
                    activeView === "text"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Tam Metin
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView("ai")}
                  className={`rounded-[var(--radius-xl)] px-3 py-1.5 text-xs font-medium transition ${
                    activeView === "ai"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  AI Yardımı
                </button>
              </div>
            ) : null}
          </div>
          {detail ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="rounded-full">{detail.daire}</Badge>
                {detail.outcome ? (
                  <Badge variant="secondary" className="rounded-full">
                    {detail.outcome}
                  </Badge>
                ) : null}
              </div>
              <h2 className="text-lg font-semibold leading-7 text-foreground">
                {detail.title}
              </h2>
              <div className="flex flex-wrap gap-2">
                <InlineMeta label="Esas" value={detail.esas_no || "-"} compact />
                <InlineMeta label="Karar" value={detail.karar_no || "-"} compact />
                <InlineMeta label="Tarih" value={detail.karar_tarihi || "-"} compact />
              </div>
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden p-5 pt-0">
        {detailPending ? (
          <DetailSkeleton />
        ) : detailError ? (
          <div className="rounded-[var(--radius-2xl)] border border-destructive bg-destructive-soft p-4 text-sm text-destructive">
            {detailError}
          </div>
        ) : detail ? (
          <>
            <Separator />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-2xl)] border border-border bg-card">
              {activeView === "text" ? (
                <>
                  <div className="border-b border-border px-4 py-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                        Tam Metin
                      </p>
                      <div className="relative w-full sm:w-56">
                        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          value={documentSearch}
                          onChange={(event) => setDocumentSearch(event.target.value)}
                          placeholder="Metinde ara"
                          className="h-9 rounded-[var(--radius-xl)] pl-9 text-sm"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4">
                    <pre
                      className="max-w-full whitespace-pre-wrap break-words font-sans text-sm leading-8 text-foreground [word-break:break-word]"
                      dangerouslySetInnerHTML={{ __html: highlightedFullText }}
                    />
                  </div>
                </>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                  <div className="border-b border-border px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                        AI Yardımı
                      </p>
                      {!decisionSummary ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={onDecisionSummaryGenerate}
                          disabled={decisionSummaryPending}
                        >
                          {decisionSummaryPending ? "Üretiliyor" : "AI özeti üret"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
                    <div className="mx-auto flex h-full w-full max-w-3xl flex-col">
                      {decisionSummary ? (
                        <div className="mb-4 space-y-2.5 rounded-[var(--radius-2xl)] border border-border bg-muted p-4">
                          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                            Seçilen karar özeti
                          </p>
                          <p className="text-sm leading-7 text-foreground">
                            {decisionSummary.short_summary}
                          </p>
                          <p className="text-sm leading-6 text-muted-foreground">
                            {decisionSummary.why_relevant}
                          </p>
                          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                            {decisionSummary.reference}
                          </p>
                        </div>
                      ) : (
                        <div className="mb-4 rounded-[var(--radius-2xl)] border border-dashed border-border bg-muted p-4 text-sm leading-7 text-muted-foreground">
                          Bu kararla ilgili kısa bir AI özeti oluşturabilir veya alttaki alanı kullanarak karar hakkında soru sorabilirsiniz.
                        </div>
                      )}
                      <DecisionChatPanel
                        question={chatQuestion}
                        answer={chatAnswer}
                        isPending={chatPending}
                        error={chatError}
                        onQuestionChange={onChatQuestionChange}
                        onSubmit={onChatSubmit}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center rounded-[var(--radius-2xl)] border border-dashed border-border bg-muted p-6 text-center text-sm text-muted-foreground">
            Listeden bir karar seçtiğinizde tam metin burada açılacak.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
