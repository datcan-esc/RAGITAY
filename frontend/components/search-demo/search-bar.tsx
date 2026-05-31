import { Loader2, Search, SlidersHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function SearchBar({
  query,
  isPending,
  onQueryChange,
  onOpenFilters,
  onSubmit,
}: {
  query: string
  isPending: boolean
  onQueryChange: (value: string) => void
  onOpenFilters: () => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
}) {
  return (
    <section className="rounded-[24px] border border-border bg-card p-3 shadow-sm">
      <form className="space-y-3" onSubmit={onSubmit}>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="Örn. iş yeri whatsapp kuralları"
              className="h-14 rounded-2xl border-transparent bg-muted pl-12 pr-4 text-base shadow-none focus-visible:border-ring"
            />
          </div>
          <Button
            type="button"
            variant="outline"
            size="lg"
            className="h-14 rounded-2xl px-4"
            onClick={onOpenFilters}
          >
            <SlidersHorizontal className="size-4" />
            Filtreler
          </Button>
          <Button type="submit" size="lg" className="h-14 rounded-2xl px-6">
            {isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Aranıyor
              </>
            ) : (
              <>
                <Search className="size-4" />
                Ara
              </>
            )}
          </Button>
        </div>
      </form>
    </section>
  )
}
