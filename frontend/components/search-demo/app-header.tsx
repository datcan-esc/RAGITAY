import { Home, Moon, Sun } from "lucide-react"

import { Button } from "@/components/ui/button"

export function AppHeader({
  isDarkMode,
  onToggleTheme,
  onGoHome,
}: {
  isDarkMode: boolean
  onToggleTheme: () => void
  onGoHome: () => void
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur supports-[backdrop-filter]:bg-background/55">
      <div className="mx-auto flex h-[3.25rem] w-full max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="rounded-full"
          onClick={onGoHome}
          aria-label="Ana sayfaya dön"
        >
          <Home className="size-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="rounded-full"
          onClick={onToggleTheme}
          aria-label={isDarkMode ? "Açık temaya geç" : "Koyu temaya geç"}
        >
          {isDarkMode ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
      </div>
    </header>
  )
}
