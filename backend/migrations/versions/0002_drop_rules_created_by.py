"""Drop rules.created_by (it stored the client IP address, personal data)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain ALTER TABLE ... DROP COLUMN: valid online and in offline (--sql) mode
    # (SQLite supports it since 3.35, PostgreSQL always)
    op.drop_column("rules", "created_by")


def downgrade() -> None:
    # The dropped values are not recoverable: the column comes back empty
    op.add_column("rules", sa.Column("created_by", sa.String(length=100), nullable=True))
