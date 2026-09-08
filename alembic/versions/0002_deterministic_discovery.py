"""Add deterministic source discovery and usage tracking.

Revision ID: 0002_discovery
Revises: 0001_initial
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_discovery"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("news_url", sa.String(length=500), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "article_url_patterns",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.execute("UPDATE sources SET news_url = website_url WHERE news_url IS NULL")
    op.alter_column("sources", "news_url", nullable=False)

    op.create_table(
        "source_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("classification_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("ix_source_entries_source_id", "source_entries", ["source_id"])
    op.create_index("ix_source_entries_published_at", "source_entries", ["published_at"])
    op.create_index("ix_source_entries_status", "source_entries", ["status"])

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("discovered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("classified_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("saved_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_runs_source_id", "scan_runs", ["source_id"])

    op.add_column("news_items", sa.Column("source_entry_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        "uq_news_items_source_entry_id", "news_items", ["source_entry_id"]
    )
    op.create_foreign_key(
        "fk_news_items_source_entry_id",
        "news_items",
        "source_entries",
        ["source_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_news_items_source_entry_id", "news_items", type_="foreignkey")
    op.drop_constraint("uq_news_items_source_entry_id", "news_items", type_="unique")
    op.drop_column("news_items", "source_entry_id")
    op.drop_table("scan_runs")
    op.drop_table("source_entries")
    op.drop_column("sources", "article_url_patterns")
    op.drop_column("sources", "news_url")
