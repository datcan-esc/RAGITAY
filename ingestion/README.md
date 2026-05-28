## Ingestion Layout

This directory contains the data ingestion pipeline.

High-level flow:

1. `discover`
   - Queries `aramadetaylist`
   - Saves one merged search JSON
2. `fetch`
   - Reads discovered `id` values
   - Downloads raw documents from the configured document endpoint
3. `parse`
   - Reads raw document JSON files
   - Produces normalized decision JSON files
4. `collect`
   - Convenience wrapper that runs all three steps

Suggested command order:

```bash
python3 ingestion/scripts/yargitay_cli.py discover --query '"işe iade"' --decision-year 2022 --max-pages 2
python3 ingestion/scripts/yargitay_cli.py fetch --run-name ise-iade-2022 --source-name yargitay
python3 ingestion/scripts/yargitay_cli.py parse --run-name ise-iade-2022 --source-name yargitay
```

Default batch run:

```bash
python3 ingestion/scripts/yargitay_cli.py run-wordlist
```

Shortest usage:

```bash
python3 ingestion/scripts/yargitay_cli.py --profile yargitay
python3 ingestion/scripts/yargitay_cli.py --profile uyap
```

Full pipeline in one command:

```bash
python3 scripts/run_pipeline.py
```

This runs, in order:

1. `--profile yargitay`
2. `--profile uyap`
3. `import_decisions.py`
4. `build_chunks.py`
5. `build_embeddings.py`

This command reads:

- `ingestion/config/profiles/default.json`
- profile icinde tanimli wordlist dosyasi

Available profiles:

- `default.json`: Yargıtay karar arama
- `uyap_emsal.json`: UYAP emsal arama

Default wordlists:

- `wordlists/yargitay_queries.txt`
- `wordlists/uyap_queries.txt`

Example UYAP run:

```bash
python3 ingestion/scripts/yargitay_cli.py run-wordlist \
  --profile ingestion/config/profiles/uyap_emsal.json \
  --profile-name uyap
```

Import parsed kararlar into PostgreSQL:

```bash
python3 ingestion/scripts/import_decisions.py
```

Optional examples:

```bash
python3 ingestion/scripts/import_decisions.py --source-name yargitay
python3 ingestion/scripts/import_decisions.py --source-name uyap_emsal
python3 ingestion/scripts/import_decisions.py --limit 100 --verbose
```

Build decision chunks:

```bash
python3 ingestion/scripts/build_chunks.py
```

Optional examples:

```bash
python3 ingestion/scripts/build_chunks.py --source-name yargitay
python3 ingestion/scripts/build_chunks.py --source-name uyap_emsal
python3 ingestion/scripts/build_chunks.py --limit 200 --verbose
python3 ingestion/scripts/build_chunks.py --rebuild
```

Build chunk embeddings:

```bash
python3 ingestion/scripts/build_embeddings.py
```

Optional examples:

```bash
python3 ingestion/scripts/build_embeddings.py --source-name yargitay
python3 ingestion/scripts/build_embeddings.py --source-name uyap_emsal
python3 ingestion/scripts/build_embeddings.py --limit 500 --batch-size 24 --verbose
python3 ingestion/scripts/build_embeddings.py --rebuild
```

And tracks completed jobs in:

- `ingestion/state/done_jobs.txt`
- `ingestion/state/failed_jobs.txt`

Data layout:

```text
ingestion/
  config/
    profiles/
      default.json
      uyap_emsal.json
    wordlists/
      example_queries.txt
  output/
    yargitay/
      searches/
        <run-name>.json
      documents/
        <id>.json
      parsed/
        <id>.json
    uyap_emsal/
      searches/
        <run-name>.json
      documents/
        <id>.json
      parsed/
        <id>.json
  scripts/
    yargitay_cli.py
  state/
    done_jobs.txt
    failed_jobs.txt
  src/
    ragitay/
      parser.py
      paths.py
      pipeline.py
      yargitay_client.py
```
