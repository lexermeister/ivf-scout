# IVF Scout

Minimal V1 for deterministically discovering configured IVF-industry announcements and storing
only relevant news.

## Local setup

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Start PostgreSQL:

   ```bash
   docker compose up -d db
   ```

3. Create a virtual environment and install the project:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install '.[dev]'
   ```

4. Create the schema and seed the initial sources:

   ```bash
   .venv/bin/ivf-scout db-upgrade
   .venv/bin/ivf-scout seed-sources
   ```

5. Scan all enabled sources:

   ```bash
   .venv/bin/ivf-scout scan
   ```

6. Inspect stored results:

   ```bash
   .venv/bin/ivf-scout list-news
   ```

Scan one source with a 14-day lookback, including if that source was already scanned:

```bash
.venv/bin/ivf-scout scan --source cooper-surgical --days 14
```

## V1 scope

- Sources are stored in PostgreSQL and can be enabled or disabled.
- Each source has a configured news index and allowed article URL patterns.
- HTML and PDF links are discovered and fetched directly without OpenAI web search.
- Every discovered URL is recorded in `source_entries`; known URLs are not classified again.
- Newly discovered undated articles remain eligible and keep `published_at` empty.
- New article content is classified in small batches with structured OpenAI output.
- Only named new-product introductions, launches, launch-enabling approvals, and substantive
  product unveilings are retained; regulatory-only and general industry stories are excluded.
- Reports show the product name and a concise product description for every retained item.
- Relevant results are stored in `news_items`.
- Token usage and estimated model cost are stored in `scan_runs` and printed by the CLI.
- An exact URL is stored only once; there is no semantic deduplication.

On a quiet day, when all links are already known, the scan makes no OpenAI request.

## Scanner configuration

The inexpensive content classifier defaults to `gpt-5.6-luna`. Pricing inputs are configurable so
the CLI estimate can be kept aligned with the selected model:

```dotenv
OPENAI_MODEL=gpt-5.6-luna
DISCOVERY_MAX_CANDIDATES=20
CLASSIFIER_BATCH_SIZE=5
ARTICLE_MAX_CHARACTERS=12000
OPENAI_INPUT_COST_PER_MILLION=0.20
OPENAI_OUTPUT_COST_PER_MILLION=1.20
```
