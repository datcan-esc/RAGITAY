import { Loader2, Search, SlidersHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export function SearchBar({
  query,
  isPending,
  onQueryChange,
  onOpenFilters,
  onSubmit,
  mode = "results",
}: {
  query: string
  isPending: boolean
  onQueryChange: (value: string) => void
  onOpenFilters: () => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  mode?: "landing" | "results"
}) {
  const isLanding = mode === "landing"

  return (
    <section

    >
      <form className="space-y-3" onSubmit={onSubmit}>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="Örn. WhatsApp mesajlarına cevap vermediğim için işten çıkarıldım"
              className={cn(
                "rounded-[var(--radius-2xl)] pl-12 pr-4 text-base shadow-none focus-visible:border-ring",
                isLanding ? "h-16 text-[15px]" : "h-14",
              )}
            />
          </div>
          <Button
            type="button"
            variant="outline"
            size="lg"
            className={cn("rounded-[var(--radius-2xl)] px-4", isLanding ? "h-16" : "h-14")}
            onClick={onOpenFilters}
          >
            <SlidersHorizontal className="size-4" />
            Filtreler
          </Button>
          <Button
            type="submit"
            size="lg"
            className={cn("rounded-[var(--radius-2xl)] px-6", isLanding ? "h-16" : "h-14")}
          >
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
