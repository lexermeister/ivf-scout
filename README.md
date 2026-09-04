# IVF Scout

Minimal V1 for scanning configured IVF-industry sources and storing relevant news.

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
- Each source is searched only within its configured domain.
- OpenAI web search returns structured relevant-news results.
- Relevant results are stored in `news_items`.
- An exact URL is stored only once; there is no semantic or cross-source deduplication.
