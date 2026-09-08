from __future__ import annotations

import logging
from pathlib import Path

import typer
from alembic.config import Config

from alembic import command
from ivf_scout.config import get_settings
from ivf_scout.db.repositories import NewsRepository, SourceRepository
from ivf_scout.db.session import create_database_engine, create_session_factory, session_scope
from ivf_scout.scanning.classifier import OpenAIContentClassifier
from ivf_scout.scanning.discovery import SourceDiscoverer
from ivf_scout.scanning.documents import ArticleFetcher
from ivf_scout.scanning.service import ScanService
from ivf_scout.seeds import INITIAL_SOURCES

app = typer.Typer(no_args_is_help=True, help="Scan IVF industry sources for relevant news.")


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _session_factory():
    return create_session_factory(create_database_engine())


@app.command("db-upgrade")
def db_upgrade() -> None:
    """Apply all database migrations."""
    project_root = Path.cwd()
    config_path = project_root / "alembic.ini"
    if not config_path.exists():
        raise typer.BadParameter("Run db-upgrade from the project root containing alembic.ini")
    config = Config(str(config_path))
    config.set_main_option("script_location", str(project_root / "alembic"))
    command.upgrade(config, "head")
    typer.echo("Database schema is up to date.")


@app.command("seed-sources")
def seed_sources() -> None:
    """Insert or update the initial source registry."""
    with session_scope(_session_factory()) as session:
        repository = SourceRepository(session)
        for seed in INITIAL_SOURCES:
            repository.upsert_seed(seed)
    typer.echo(f"Seeded {len(INITIAL_SOURCES)} sources.")


@app.command("list-sources")
def list_sources() -> None:
    """List enabled sources."""
    with session_scope(_session_factory()) as session:
        for source in SourceRepository(session).list_enabled():
            typer.echo(f"{source.slug}: {source.name} ({source.domain})")


@app.command("list-news")
def list_news(
    limit: int = typer.Option(20, min=1, max=100, help="Maximum number of items to show."),
) -> None:
    """List recently discovered relevant news."""
    with session_scope(_session_factory()) as session:
        items = NewsRepository(session).list_recent(limit)
        if not items:
            typer.echo("No news items stored yet.")
            return
        for item in items:
            published = item.published_at.isoformat() if item.published_at else "date unknown"
            typer.echo(f"[{item.category}] {published} — {item.title}")
            typer.echo(f"  {item.url}")


@app.command()
def scan(
    source: str | None = typer.Option(None, help="Scan only this source slug."),
    days: int | None = typer.Option(
        None,
        min=1,
        max=90,
        help="Lookback in days, including for previously scanned sources.",
    ),
) -> None:
    """Scan all enabled sources and store relevant news."""
    _configure_logging()
    settings = get_settings()
    if not settings.openai_api_key:
        raise typer.BadParameter(
            "OPENAI_API_KEY is required. Copy .env.example to .env and add your key."
        )
    discoverer = SourceDiscoverer(settings.discovery_max_candidates)
    fetcher = ArticleFetcher(settings.article_max_characters)
    classifier = OpenAIContentClassifier(settings)
    with session_scope(_session_factory()) as session:
        service = ScanService(
            session,
            discoverer,
            fetcher,
            classifier,
            days or settings.scan_lookback_days,
            settings.classifier_batch_size,
            settings.openai_input_cost_per_million,
            settings.openai_output_cost_per_million,
        )
        summary = service.run(source_slug=source)

    for outcome in summary.outcomes:
        window = f"{outcome.start_date} to {outcome.end_date}"
        if outcome.status == "SUCCEEDED":
            typer.echo(
                f"{outcome.source}: scanned {window}; {outcome.discovered} discovered, "
                f"{outcome.new} new, {outcome.skipped} skipped, "
                f"{outcome.classified} classified, {outcome.saved} relevant saved"
            )
            typer.echo(
                f"  OpenAI usage: {outcome.input_tokens} input + "
                f"{outcome.output_tokens} output tokens; "
                f"estimated cost ${outcome.estimated_cost_usd:.6f}"
            )
            if outcome.entry_failures:
                typer.echo(f"  Entry failures: {outcome.entry_failures}", err=True)
        else:
            typer.echo(f"{outcome.source}: scanned {window}; failed — {outcome.error}", err=True)
    typer.echo(
        f"Completed: {summary.succeeded} succeeded, {summary.failed} failed, "
        f"{summary.saved} items saved"
    )
    if summary.failed and not summary.succeeded:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
