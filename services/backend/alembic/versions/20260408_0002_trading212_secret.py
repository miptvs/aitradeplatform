"""add trading212 api secret

Revision ID: 20260408_0002
Revises: 20260403_0001
Create Date: 2026-04-08 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260408_0002"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("broker_accounts", sa.Column("encrypted_api_secret", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("broker_accounts", "encrypted_api_secret")
