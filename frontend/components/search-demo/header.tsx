import { Moon, Sun } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function SearchHeader({
  isDarkMode,
  onToggleTheme,
  mode = "results",
}: {
  isDarkMode: boolean
  onToggleTheme: () => void
  mode?: "landing" | "results"
}) {
  const isLanding = mode === "landing"

  return (
    <header
      className={cn(
        "mx-auto flex w-full flex-col",
        isLanding ? "max-w-3xl gap-6 text-center" : "max-w-6xl gap-4 pb-6",
      )}
    >
      <div
        className={cn(
          "flex gap-4",
          isLanding ? "items-start justify-end" : "items-start justify-between",
        )}
      >
        <div className={cn("space-y-2", isLanding ? "w-full pr-10" : "")}>
          <p className="text-sm font-medium tracking-[0.18em] text-muted-foreground uppercase">
            RAGITAY
          </p>
          <h1
            className={cn(
              "font-semibold tracking-tight",
              isLanding ? "text-5xl sm:text-6xl" : "text-3xl sm:text-4xl",
            )}
          >
            Emsal kararlarla konuşun
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
      <div className={cn(isLanding ? "mx-auto max-w-2xl" : "max-w-2xl")}>
        <p className="text-base leading-7 text-muted-foreground">
          {isLanding
            ? "Yargıtay ve UYAP kararlarını doğal dilde arayın, ilgili sonuçları görün ve seçtiğiniz kararın tam metnini inceleyin."
            : "Arama sonuçlarını karşılaştırın, özeti okuyun ve seçtiğiniz kararın tam metnine geçin."}
        </p>
      </div>
    </header>
  )
}
