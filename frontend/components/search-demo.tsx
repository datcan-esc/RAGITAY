"use client"

import { usePathname, useRouter } from "next/navigation"
import { startTransition, useEffect, useRef, useState } from "react"

import { ActiveFilters } from "@/components/search-demo/active-filters"
import { AppHeader } from "@/components/search-demo/app-header"
import { DetailPanel } from "@/components/search-demo/detail-panel"
import { FiltersModal } from "@/components/search-demo/filters-modal"
import { SearchHeader } from "@/components/search-demo/header"
import { ResultsList } from "@/components/search-demo/results-list"
import { SearchBar } from "@/components/search-demo/search-bar"
import { SummaryCard } from "@/components/search-demo/summary-card"
import type {
  DecisionChatResponse,
  DecisionDetail,
  DecisionSummaryResponse,
  SearchError,
  SearchResponse,
  SummaryResponse,
} from "@/components/search-demo/types"

const API_BASE_URL =
  process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL ?? "http://127.0.0.1:8000"

const SOURCE_OPTIONS = [
  { id: "yargitay", label: "Yargıtay" },
  { id: "uyap_emsal", label: "UYAP Emsal" },
]

type SearchControls = {
  query: string
  sourceNames: string[]
  daire: string
  yearFrom: string
  yearTo: string
  topDecisions: string
}

export function SearchDemo() {
  const router = useRouter()
  const pathname = usePathname()
  const initialUrlAppliedRef = useRef(false)
  const [query, setQuery] = useState("")
  const [sourceNames, setSourceNames] = useState<string[]>(["yargitay"])
  const [daire, setDaire] = useState("9. Hukuk Dairesi")
  const [yearFrom, setYearFrom] = useState("2020")
  const [yearTo, setYearTo] = useState("2026")
  const [topDecisions, setTopDecisions] = useState("5")
  const [hasSearched, setHasSearched] = useState(false)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [summaryPending, setSummaryPending] = useState(false)
  const [error, setError] = useState("")
  const [isPending, setIsPending] = useState(false)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [activeDecisionId, setActiveDecisionId] = useState<number | null>(null)
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [detailError, setDetailError] = useState("")
  const [detailPending, setDetailPending] = useState(false)
  const [decisionSummary, setDecisionSummary] = useState<DecisionSummaryResponse | null>(null)
  const [decisionSummaryPending, setDecisionSummaryPending] = useState(false)
  const [decisionQuestion, setDecisionQuestion] = useState("")
  const [decisionAnswer, setDecisionAnswer] = useState<DecisionChatResponse | null>(null)
  const [decisionChatPending, setDecisionChatPending] = useState(false)
  const [decisionChatError, setDecisionChatError] = useState("")
  const [isDarkMode, setIsDarkMode] = useState(false)

  function buildSearchControls(
    override?: Partial<SearchControls>
  ): SearchControls {
    return {
      query: override?.query ?? query,
      sourceNames: override?.sourceNames ?? sourceNames,
      daire: override?.daire ?? daire,
      yearFrom: override?.yearFrom ?? yearFrom,
      yearTo: override?.yearTo ?? yearTo,
      topDecisions: override?.topDecisions ?? topDecisions,
    }
  }

  function syncUrl(nextControls: SearchControls) {
    const params = new URLSearchParams()
    const trimmedQuery = nextControls.query.trim()

    if (trimmedQuery) {
      params.set("q", trimmedQuery)
    }
    if (nextControls.sourceNames.length) {
      params.set("sources", nextControls.sourceNames.join(","))
    }
    if (nextControls.daire.trim()) {
      params.set("daire", nextControls.daire.trim())
    }
    if (nextControls.yearFrom) {
      params.set("from", nextControls.yearFrom)
    }
    if (nextControls.yearTo) {
      params.set("to", nextControls.yearTo)
    }
    if (nextControls.topDecisions) {
      params.set("top", nextControls.topDecisions)
    }

    const nextUrl = params.toString() ? `${pathname}?${params.toString()}` : pathname
    router.push(nextUrl, { scroll: false })
  }

  function resetSearchState() {
    setQuery("")
    setSourceNames(["yargitay"])
    setDaire("9. Hukuk Dairesi")
    setYearFrom("2020")
    setYearTo("2026")
    setTopDecisions("5")
    setHasSearched(false)
    setData(null)
    setSummary(null)
    setError("")
    setActiveDecisionId(null)
    setDetail(null)
    setDetailError("")
    setDecisionSummary(null)
    setDecisionQuestion("")
    setDecisionAnswer(null)
    setDecisionChatError("")
    router.push(pathname, { scroll: false })
  }

  async function runSearch(override?: Partial<SearchControls>) {
    const nextControls = buildSearchControls(override)
    const nextQuery = nextControls.query.trim()
    if (!nextQuery) {
      setError("Arama sorgusu boş olamaz.")
      return
    }

    setQuery(nextControls.query)
    setSourceNames(nextControls.sourceNames)
    setDaire(nextControls.daire)
    setYearFrom(nextControls.yearFrom)
    setYearTo(nextControls.yearTo)
    setTopDecisions(nextControls.topDecisions)
    setHasSearched(true)
    setIsPending(true)
    setError("")
    syncUrl(nextControls)

    try {
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: nextQuery,
          source_names: nextControls.sourceNames,
          daire: nextControls.daire.trim() || undefined,
          year_from: nextControls.yearFrom ? Number(nextControls.yearFrom) : undefined,
          year_to: nextControls.yearTo ? Number(nextControls.yearTo) : undefined,
          top_decisions: Number(nextControls.topDecisions),
        }),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as SearchError
        throw new Error(body.detail || "Arama sırasında beklenmeyen bir hata oluştu.")
      }

      const body = (await response.json()) as SearchResponse
      setData(body)
      setSummary(null)

      if (body.results.length) {
        void runSummary(body)
      }

      const firstDecisionId = body.results[0]?.decision_id ?? null
      setActiveDecisionId(firstDecisionId)
      setDetail(null)
      setDetailError("")
      setDecisionSummary(null)
      setDecisionAnswer(null)
      setDecisionChatError("")
      setDecisionQuestion("")

      if (firstDecisionId) {
        void loadDecisionDetail(firstDecisionId)
      }
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Arama sırasında beklenmeyen bir hata oluştu."
      setError(message)
      setData(null)
      setSummary(null)
      setActiveDecisionId(null)
      setDetail(null)
    } finally {
      setIsPending(false)
    }
  }

  async function runSummary(searchData: SearchResponse) {
    setSummaryPending(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/search/summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchData.query,
          results: searchData.results.map((result) => ({
            decision_id: result.decision_id,
            title: result.title,
            daire: result.daire,
            esas_no: result.esas_no,
            karar_no: result.karar_no,
            karar_tarihi: result.karar_tarihi,
            outcome: result.outcome,
            passages: result.passages.map((passage) => ({
              section_name: passage.section_name,
              chunk_text: passage.chunk_text,
            })),
          })),
        }),
      })

      if (!response.ok) {
        throw new Error("Özet alınamadı.")
      }

      const body = (await response.json()) as SummaryResponse
      setSummary(body)
    } catch {
      setSummary(null)
    } finally {
      setSummaryPending(false)
    }
  }

  async function loadDecisionDetail(decisionId: number) {
    setActiveDecisionId(decisionId)
    setDetailPending(true)
    setDetailError("")
    setDecisionSummary(null)
    setDecisionAnswer(null)
    setDecisionChatError("")
    setDecisionQuestion("")

    try {
      const response = await fetch(`${API_BASE_URL}/api/search/decisions/${decisionId}`)
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as SearchError
        throw new Error(body.detail || "Karar detayı alınamadı.")
      }

      const body = (await response.json()) as DecisionDetail
      setDetail(body)
    } catch (caughtError) {
      const message =
        caughtError instanceof Error ? caughtError.message : "Karar detayı alınamadı."
      setDetail(null)
      setDetailError(message)
    } finally {
      setDetailPending(false)
    }
  }

  async function generateDecisionSummary() {
    if (!activeDecisionId || query.trim().length < 2) {
      return
    }

    setDecisionSummaryPending(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/search/decisions/${activeDecisionId}/summary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: query.trim(),
        }),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as SearchError
        throw new Error(body.detail || "Karar özeti üretilemedi.")
      }

      const body = (await response.json()) as DecisionSummaryResponse
      setDecisionSummary(body)
    } catch {
      setDecisionSummary(null)
    } finally {
      setDecisionSummaryPending(false)
    }
  }

  async function askDecisionQuestion() {
    if (!activeDecisionId || decisionQuestion.trim().length < 3) {
      return
    }

    setDecisionChatPending(true)
    setDecisionChatError("")
    try {
      const response = await fetch(`${API_BASE_URL}/api/search/decisions/${activeDecisionId}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: decisionQuestion.trim(),
        }),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as SearchError
        throw new Error(body.detail || "Karar sorusu cevaplanamadı.")
      }

      const body = (await response.json()) as DecisionChatResponse
      setDecisionAnswer(body)
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Karar sorusu cevaplanamadı."
      setDecisionChatError(message)
      setDecisionAnswer(null)
    } finally {
      setDecisionChatPending(false)
    }
  }

  useEffect(() => {
    const root = document.documentElement
    const savedTheme = window.localStorage.getItem("ragitay-theme")
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
    const nextTheme = savedTheme ? savedTheme === "dark" : prefersDark

    root.classList.toggle("dark", nextTheme)
    window.localStorage.setItem("ragitay-theme", nextTheme ? "dark" : "light")
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDarkMode(nextTheme)
  }, [])

  useEffect(() => {
    if (initialUrlAppliedRef.current) {
      return
    }

    initialUrlAppliedRef.current = true

    const params = new URLSearchParams(window.location.search)
    const initialQuery = params.get("q")?.trim() ?? ""
    if (!initialQuery) {
      return
    }

    const initialSources = params
      .get("sources")
      ?.split(",")
      .map((value) => value.trim())
      .filter(Boolean)

    const initialControls: SearchControls = {
      query: initialQuery,
      sourceNames: initialSources?.length ? initialSources : ["yargitay"],
      daire: params.get("daire") ?? "9. Hukuk Dairesi",
      yearFrom: params.get("from") ?? "2020",
      yearTo: params.get("to") ?? "2026",
      topDecisions: params.get("top") ?? "5",
    }

    startTransition(() => {
      void runSearch(initialControls)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleTheme() {
    const nextTheme = !isDarkMode
    const root = document.documentElement

    root.classList.toggle("dark", nextTheme)
    window.localStorage.setItem("ragitay-theme", nextTheme ? "dark" : "light")
    setIsDarkMode(nextTheme)
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    startTransition(() => {
      void runSearch()
    })
  }

  function toggleSource(nextSource: string) {
    setSourceNames((current) => {
      if (current.includes(nextSource)) {
        if (current.length === 1) {
          return current
        }
        return current.filter((item) => item !== nextSource)
      }
      return [...current, nextSource]
    })
  }

  const showLanding = !hasSearched && !isPending
  return (
    <div className="min-h-screen bg-background text-foreground">
      <AppHeader
        isDarkMode={isDarkMode}
        onToggleTheme={toggleTheme}
        onGoHome={resetSearchState}
      />
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col px-4 pb-10 pt-8 sm:px-6 lg:px-8">
        {showLanding ? (
          <main className="flex flex-1 items-center justify-center">
            <div className="flex w-full max-w-4xl flex-col gap-10">
              <SearchHeader mode="landing" />
              <div className="mx-auto w-full max-w-3xl">
                <SearchBar
                  query={query}
                  isPending={isPending}
                  onQueryChange={setQuery}
                  onOpenFilters={() => setFiltersOpen(true)}
                  onSubmit={handleSubmit}
                  mode="landing"
                />
              </div>
            </div>
          </main>
        ) : (
          <>
            <SearchHeader mode="results" />

            <main className="flex flex-col gap-5">
              <SearchBar
                query={query}
                isPending={isPending}
                onQueryChange={setQuery}
                onOpenFilters={() => setFiltersOpen(true)}
                onSubmit={handleSubmit}
              />
              <ActiveFilters
                sourceLabels={SOURCE_OPTIONS.filter((option) => sourceNames.includes(option.id)).map(
                  (option) => option.label
                )}
                daire={daire}
                yearFrom={yearFrom}
                yearTo={yearTo}
                topDecisions={topDecisions}
              />

              {error ? (
                <section className="rounded-[var(--radius-2xl)] border border-destructive bg-destructive-soft px-4 py-3 text-sm text-destructive">
                  {error}
                </section>
              ) : null}

              <SummaryCard
                isPending={isPending || summaryPending}
                summary={summary}
                resultCount={data?.results.length ?? 0}
              />

              <section className="grid gap-5 lg:grid-cols-[minmax(0,0.78fr)_minmax(420px,1.02fr)]">
                <div className="space-y-3">
                  <ResultsList
                    isPending={isPending}
                    results={data?.results ?? []}
                    activeDecisionId={activeDecisionId}
                    onSelect={(decisionId) => void loadDecisionDetail(decisionId)}
                  />
                </div>

        <DetailPanel
          key={activeDecisionId ?? "empty-detail"}
          detail={detail}
          detailError={detailError}
          detailPending={detailPending}
                  decisionSummary={decisionSummary?.decision_summary ?? null}
                  decisionSummaryPending={decisionSummaryPending}
                  highlightTerms={[query, decisionQuestion]}
                  chatQuestion={decisionQuestion}
                  chatAnswer={decisionAnswer}
                  chatPending={decisionChatPending}
                  chatError={decisionChatError}
                  onChatQuestionChange={setDecisionQuestion}
                  onChatSubmit={() => {
                    startTransition(() => {
                      void askDecisionQuestion()
                    })
                  }}
                  onDecisionSummaryGenerate={() => {
                    startTransition(() => {
                      void generateDecisionSummary()
                    })
                  }}
                />
              </section>
            </main>
          </>
        )}
      </div>

      <FiltersModal
        isOpen={filtersOpen}
        sourceOptions={SOURCE_OPTIONS}
        sourceNames={sourceNames}
        daire={daire}
        yearFrom={yearFrom}
        yearTo={yearTo}
        topDecisions={topDecisions}
        onToggleSource={toggleSource}
        onClose={() => setFiltersOpen(false)}
        onApply={() => {
          setFiltersOpen(false)
          startTransition(() => {
            void runSearch()
          })
        }}
        onDaireChange={setDaire}
        onYearFromChange={setYearFrom}
        onYearToChange={setYearTo}
        onTopDecisionsChange={setTopDecisions}
      />
    </div>
  )
}
