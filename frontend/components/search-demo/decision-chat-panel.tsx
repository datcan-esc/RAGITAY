import { ArrowUp, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import type { DecisionChatResponse } from "./types"

export function DecisionChatPanel({
  question,
  answer,
  isPending,
  error,
  onQuestionChange,
  onSubmit,
}: {
  question: string
  answer: DecisionChatResponse | null
  isPending: boolean
  error: string
  onQuestionChange: (value: string) => void
  onSubmit: () => void
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {answer ? (
          <div className="space-y-3 rounded-[var(--radius-2xl)] border border-border bg-muted p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className="rounded-full">
                {answer.provider}
              </Badge>
              <Badge variant="outline" className="rounded-full">
                {answer.model}
              </Badge>
            </div>
            <p className="text-sm leading-7 text-foreground">{answer.answer}</p>
            {answer.key_points.length ? (
              <div className="space-y-2">
                {answer.key_points.map((point) => (
                  <div key={point} className="flex items-start gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-foreground" />
                    <p className="text-sm leading-7 text-foreground">{point}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
              {answer.reference}
            </p>
          </div>
        ) : (
          <div className="rounded-[var(--radius-2xl)] border border-dashed border-border bg-muted p-4 text-sm leading-7 text-muted-foreground">
            Sorunuzun cevabı burada görünecek. Yanıt yalnızca seçtiğiniz kararın metnine dayanır.
          </div>
        )}

        {error ? (
          <div className="rounded-[var(--radius-2xl)] border border-destructive bg-destructive-soft p-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}
      </div>

      <div className="mt-4 border-t border-border pt-3">
        <div className="flex items-center gap-2 rounded-[var(--radius-2xl)]">
          <Input
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder="Yapay zeka ile karar hakkında konuş"
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                onSubmit()
              }
            }}
          />
          <Button
            type="button"
            size="icon"
            className="rounded-[var(--radius-xl)]"
            onClick={onSubmit}
            disabled={isPending || question.trim().length < 3}
            aria-label="Karar hakkında soru sor"
          >
            {isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
