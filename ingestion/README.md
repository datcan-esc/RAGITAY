## Ingestion Layout

This directory contains the data ingestion pipeline.

High-level flow:

1. `discover`
   - Queries `aramadetaylist`
   - Saves page responses
   - Builds a manifest and `hits.jsonl`
2. `fetch`
   - Reads discovered `id` values
   - Downloads raw documents from `getDokuman`
3. `parse`
   - Reads raw document JSON files
   - Produces normalized decision JSON files
4. `collect`
   - Convenience wrapper that runs all three steps

Suggested command order:

```bash
python3 ingestion/scripts/yargitay_cli.py discover --query '"işe iade"' --decision-year 2022 --max-pages 2
python3 ingestion/scripts/yargitay_cli.py fetch --run-name ise-iade-2022
python3 ingestion/scripts/yargitay_cli.py parse --run-name ise-iade-2022
```

Default batch run:

```bash
python3 ingestion/scripts/yargitay_cli.py run-wordlist
```

This command reads:

- `ingestion/config/profiles/default.json`
- `ingestion/config/wordlists/example_queries.txt`

And tracks completed jobs in:

- `ingestion/state/done_jobs.txt`
- `ingestion/state/failed_jobs.txt`

Data layout:

```text
ingestion/
  config/
    profiles/
      default.json
    wordlists/
      example_queries.txt
  data/
    raw/
      discovery/
        <run-name>/
          pages/
            page-0001.json
          hits.jsonl
          manifest.json
      documents/
        <id>.json
    processed/
      decisions/
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
