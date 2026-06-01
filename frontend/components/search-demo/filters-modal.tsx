import { Filter, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { FilterField } from "./filter-field"
import type { SourceOption } from "./types"

export function FiltersModal({
  isOpen,
  sourceOptions,
  sourceNames,
  daire,
  yearFrom,
  yearTo,
  topDecisions,
  onToggleSource,
  onClose,
  onApply,
  onDaireChange,
  onYearFromChange,
  onYearToChange,
  onTopDecisionsChange,
}: {
  isOpen: boolean
  sourceOptions: SourceOption[]
  sourceNames: string[]
  daire: string
  yearFrom: string
  yearTo: string
  topDecisions: string
  onToggleSource: (nextSource: string) => void
  onClose: () => void
  onApply: () => void
  onDaireChange: (value: string) => void
  onYearFromChange: (value: string) => void
  onYearToChange: (value: string) => void
  onTopDecisionsChange: (value: string) => void
}) {
  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end bg-overlay p-4 sm:p-6">
      <div className="w-full max-w-md rounded-[var(--radius-4xl)] border border-border bg-card shadow-2xl">
        <div className="flex items-center justify-between px-6 pb-3 pt-6">
          <div className="space-y-1">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Filter className="size-4" />
              Filtreler
            </h2>
            <p className="text-sm text-muted-foreground">
              Kaynak, daire ve tarih aralığını daralt.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border bg-card p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground"
            aria-label="Filtreleri kapat"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="space-y-5 px-6 py-4">
          <FilterField label="Kaynak">
            <div className="flex flex-wrap gap-2">
              {sourceOptions.map((option) => {
                const active = sourceNames.includes(option.id)
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => onToggleSource(option.id)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-sm transition-colors",
                      active
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-surface text-foreground hover:bg-muted"
                    )}
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
          </FilterField>

          <FilterField label="Daire">
            <Input
              value={daire}
              onChange={(event) => onDaireChange(event.target.value)}
              placeholder="Örn. 9. Hukuk Dairesi"
            />
          </FilterField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FilterField label="Başlangıç yılı">
              <Input
                value={yearFrom}
                onChange={(event) => onYearFromChange(event.target.value)}
                inputMode="numeric"
              />
            </FilterField>
            <FilterField label="Bitiş yılı">
              <Input
                value={yearTo}
                onChange={(event) => onYearToChange(event.target.value)}
                inputMode="numeric"
              />
            </FilterField>
          </div>

          <FilterField label="Karar sayısı">
            <Input
              value={topDecisions}
              onChange={(event) => onTopDecisionsChange(event.target.value)}
              inputMode="numeric"
            />
          </FilterField>
        </div>
        <div className="flex justify-end gap-3 px-6 pb-6 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Kapat
          </Button>
          <Button type="button" onClick={onApply}>
            Uygula
          </Button>
        </div>
      </div>
    </div>
  )
}
