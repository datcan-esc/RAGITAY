from __future__ import annotations

from typing import Optional

from pgvector.psycopg import Vector

from backend.app.db import get_connection


SEARCH_SQL = """
WITH semantic_candidates AS (
  SELECT
    dc.id AS chunk_id,
    dc.decision_id,
    1 - (dc.embedding <=> %s) AS semantic_score
  FROM decision_chunks dc
  JOIN decisions d ON d.id = dc.decision_id
  WHERE dc.embedding IS NOT NULL
    AND dc.chunk_text <> ''
    {filters}
  ORDER BY dc.embedding <=> %s ASC, d.karar_tarihi DESC NULLS LAST
  LIMIT %s
),
lexical_candidates AS (
  SELECT
    dc.id AS chunk_id,
    dc.decision_id,
    GREATEST(
      similarity(lower(dc.chunk_text), lower(%s)),
      similarity(lower(d.title), lower(%s)),
      CASE WHEN lower(dc.chunk_text) LIKE %s THEN 1.0 ELSE 0.0 END,
      CASE WHEN lower(d.title) LIKE %s THEN 1.0 ELSE 0.0 END
    ) AS lexical_score
  FROM decision_chunks dc
  JOIN decisions d ON d.id = dc.decision_id
  WHERE dc.chunk_text <> ''
    {filters}
  ORDER BY lexical_score DESC, d.karar_tarihi DESC NULLS LAST
  LIMIT %s
),
candidate_ids AS (
  SELECT chunk_id FROM semantic_candidates
  UNION
  SELECT chunk_id FROM lexical_candidates
)
SELECT
  dc.id AS chunk_id,
  dc.decision_id,
  dc.chunk_index,
  dc.section_name,
  dc.chunk_text,
  d.source_name,
  d.external_id,
  d.title,
  d.daire,
  d.esas_no,
  d.karar_no,
  d.karar_tarihi,
  d.mahkeme,
  d.outcome,
  d.source_url,
  COALESCE(sc.semantic_score, 0.0) AS semantic_score,
  COALESCE(lc.lexical_score, 0.0) AS lexical_score
FROM candidate_ids c
JOIN decision_chunks dc ON dc.id = c.chunk_id
JOIN decisions d ON d.id = dc.decision_id
LEFT JOIN semantic_candidates sc ON sc.chunk_id = dc.id
LEFT JOIN lexical_candidates lc ON lc.chunk_id = dc.id
ORDER BY COALESCE(sc.semantic_score, 0.0) DESC, COALESCE(lc.lexical_score, 0.0) DESC, d.karar_tarihi DESC NULLS LAST
"""


class SearchRepository:
    def search_chunks(
        self,
        *,
        query_embedding: list[float],
        query_text: str,
        source_names: list[str],
        daire: str,
        year_from: Optional[int],
        year_to: Optional[int],
        top_k_chunks: int,
        top_k_lexical: int,
    ) -> list[dict[str, object]]:
        filter_sql, filter_params = self._build_filter_sql(
            source_names=source_names,
            daire=daire,
            year_from=year_from,
            year_to=year_to,
        )
        sql = SEARCH_SQL.format(filters=filter_sql)

        like_pattern = f"%{query_text.lower()}%"
        params: list[object] = [
            Vector(query_embedding),
            *filter_params,
            Vector(query_embedding),
            top_k_chunks,
            query_text,
            query_text,
            like_pattern,
            like_pattern,
            *filter_params,
            top_k_lexical,
        ]

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def get_decision_detail(self, decision_id: int) -> Optional[dict[str, object]]:
        sql = """
        SELECT
          id AS decision_id,
          source_name,
          external_id,
          title,
          daire,
          esas_no,
          karar_no,
          karar_tarihi,
          mahkeme,
          outcome,
          source_url,
          full_text,
          sections
        FROM decisions
        WHERE id = %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, [decision_id])
                row = cur.fetchone()
                return row if row else None

    @staticmethod
    def _build_filter_sql(
        *,
        source_names: list[str],
        daire: str,
        year_from: Optional[int],
        year_to: Optional[int],
    ) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []

        normalized_sources = [item.strip() for item in source_names if item.strip()]
        if normalized_sources:
            clauses.append("d.source_name = ANY(%s)")
            params.append(normalized_sources)

        if daire.strip():
            clauses.append("d.daire = %s")
            params.append(daire.strip())

        if year_from:
            clauses.append("d.karar_tarihi >= make_date(%s, 1, 1)")
            params.append(year_from)

        if year_to:
            clauses.append("d.karar_tarihi < make_date(%s, 1, 1)")
            params.append(year_to + 1)

        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params
