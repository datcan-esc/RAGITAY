import { cn } from "@/lib/utils"

export function SearchHeader({
  mode = "results",
}: {
  mode?: "landing" | "results"
}) {
  const isLanding = mode === "landing"

  return (
    <header
      className={cn(
        "mx-auto flex w-full flex-col",
        isLanding ? "max-w-3xl gap-6 text-center" : "max-w-6xl gap-3 pb-4",
      )}
    >
      <div className={cn("flex", isLanding ? "justify-center" : "justify-start")}>
        <div className={cn("space-y-2", isLanding ? "w-full" : "w-full")}>
          {isLanding ? (
            <>
              <p className="text-sm font-medium tracking-[0.18em] text-muted-foreground uppercase">
                RAGITAY
              </p>
              <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">
                Emsal kararlarla konuşun
              </h1>
            </>
          ) : (
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              RAGITAY
            </h1>
          )}
        </div>
      </div>
      {isLanding ? (
        <div className="mx-auto max-w-2xl">
          <p className="text-base leading-7 text-muted-foreground">
            Yargıtay ve UYAP kararlarını doğal dilde arayın, ilgili sonuçları görün ve seçtiğiniz kararın tam metnini inceleyin.
          </p>
        </div>
      ) : null}
    </header>
  )
}
