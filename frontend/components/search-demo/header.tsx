import { Moon, Sun } from "lucide-react"

import { Button } from "@/components/ui/button"

export function SearchHeader({
  isDarkMode,
  onToggleTheme,
}: {
  isDarkMode: boolean
  onToggleTheme: () => void
}) {
  return (
    <header className="mx-auto flex w-full max-w-4xl flex-col gap-4 pb-8">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-sm font-medium tracking-[0.18em] text-muted-foreground uppercase">
            RAGITAY
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Emsal karar araması
          </h1>
        </div>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="mt-1 rounded-full"
          onClick={onToggleTheme}
          aria-label={isDarkMode ? "Açık temaya geç" : "Koyu temaya geç"}
        >
          {isDarkMode ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
      </div>
      <div className="max-w-2xl">
        <p className="text-base leading-7 text-muted-foreground">
          Sorguyu yazın, filtreleri daraltın, ilgili kararı seçin ve tam metni
          temiz bir okuma alanında inceleyin.
        </p>
      </div>
    </header>
  )
}
