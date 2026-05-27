CREATE TABLE IF NOT EXISTS decisions (
  id BIGSERIAL PRIMARY KEY,
  source_name TEXT NOT NULL,
  external_id TEXT NOT NULL,
  daire TEXT NOT NULL DEFAULT '',
  esas_no TEXT NOT NULL DEFAULT '',
  karar_no TEXT NOT NULL DEFAULT '',
  karar_tarihi DATE,
  aranan_kelime TEXT NOT NULL DEFAULT '',
  durum TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  mahkeme TEXT NOT NULL DEFAULT '',
  outcome TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  run_name TEXT NOT NULL DEFAULT '',
  sections JSONB NOT NULL DEFAULT '{}'::jsonb,
  full_text TEXT NOT NULL,
  document_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_document_path TEXT NOT NULL DEFAULT '',
  parsed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source_name, external_id)
);

CREATE TABLE IF NOT EXISTS decision_chunks (
  id BIGSERIAL PRIMARY KEY,
  decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  section_name TEXT NOT NULL DEFAULT '',
  chunk_text TEXT NOT NULL,
  chunk_chars INTEGER NOT NULL DEFAULT 0,
  embedding VECTOR(768),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (decision_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_decisions_source_name ON decisions (source_name);
CREATE INDEX IF NOT EXISTS idx_decisions_karar_tarihi ON decisions (karar_tarihi DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_daire ON decisions (daire);
CREATE INDEX IF NOT EXISTS idx_decision_chunks_decision_id ON decision_chunks (decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_chunks_section_name ON decision_chunks (section_name);

CREATE INDEX IF NOT EXISTS idx_decision_chunks_trgm
  ON decision_chunks
  USING GIN (chunk_text gin_trgm_ops);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_decisions_updated_at ON decisions;

CREATE TRIGGER trg_decisions_updated_at
BEFORE UPDATE ON decisions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
