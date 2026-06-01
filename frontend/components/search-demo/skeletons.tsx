import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function ResultListSkeleton() {
  return (
    <Card className="rounded-[var(--radius-3xl)] border-border bg-card">
      <CardContent className="space-y-3 p-5">
        <Skeleton className="h-5 w-24 rounded-full" />
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-16 w-full rounded-[var(--radius-2xl)]" />
      </CardContent>
    </Card>
  )
}

export function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-5 w-28 rounded-full" />
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-16 w-full rounded-[var(--radius-2xl)]" />
      <Skeleton className="h-[420px] w-full rounded-[var(--radius-2xl)]" />
    </div>
  )
}
