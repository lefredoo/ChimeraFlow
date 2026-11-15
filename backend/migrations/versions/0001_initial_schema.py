"""Initial schema: rules, rule_executions, correlations

Revision ID: 0001
Revises:
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum names match the SQLAlchemy models (native ENUM types on PostgreSQL)
rule_status = sa.Enum("active", "inactive", "draft", name="rulestatus")
correlation_severity = sa.Enum("info", "warning", "error", name="correlationseverity")


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", rule_status, nullable=False),
        sa.Column("natural_language", sa.Text(), nullable=False),
        sa.Column("trigger", sa.JSON(), nullable=False),
        sa.Column("joins", sa.JSON(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("emit", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rule_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("correlations_found", sa.Integer(), nullable=False),
        sa.Column("records_scanned", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "correlations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", correlation_severity, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("correlations")
    op.drop_table("rule_executions")
    op.drop_table("rules")
    # PostgreSQL keeps ENUM types after their tables are dropped. Raw DROP TYPE
    # also works in offline (--sql) mode, where checkfirst cannot query the DB.
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS rulestatus")
        op.execute("DROP TYPE IF EXISTS correlationseverity")
