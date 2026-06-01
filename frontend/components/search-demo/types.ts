export type SummaryItem = {
  summary: string
  reference: string
}

export type DecisionMiniSummary = {
  decision_id: number
  reference: string
  short_summary: string
  why_relevant: string
}

export type Passage = {
  chunk_id: number
  chunk_index: number
  section_name: string
  semantic_score: number
  lexical_score: number
  adjusted_score: number
  chunk_text: string
}

export type SearchResult = {
  decision_id: number
  source_name: string
  external_id: string
  title: string
  daire: string
  esas_no: string
  karar_no: string
  karar_tarihi: string
  mahkeme: string
  outcome: string
  source_url: string
  score: number
  passages: Passage[]
}

export type SearchResponse = {
  query: string
  query_model: string
  search_mode: string
  top_k_chunks: number
  top_k_lexical: number
  top_decisions: number
  summary: SummaryItem[]
  results: SearchResult[]
}

export type SummaryResponse = {
  query: string
  general_summary: string
  key_points: string[]
  provider: string
  model: string
  fallback_used: boolean
}

export type DecisionSummaryResponse = {
  query: string
  decision_summary: DecisionMiniSummary
  provider: string
  model: string
  fallback_used: boolean
}

export type DecisionDetail = {
  decision_id: number
  source_name: string
  external_id: string
  title: string
  daire: string
  esas_no: string
  karar_no: string
  karar_tarihi: string
  mahkeme: string
  outcome: string
  source_url: string
  full_text: string
  sections: Record<string, string>
}

export type DecisionChatResponse = {
  decision_id: number
  reference: string
  answer: string
  key_points: string[]
  provider: string
  model: string
  fallback_used: boolean
}

export type SearchError = {
  detail?: string
}

export type SourceOption = {
  id: string
  label: string
}
