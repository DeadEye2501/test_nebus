"""Таблицы payments и outbox."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "currency", postgresql.ENUM("RUB", "USD", "EUR", name="currency"), nullable=False
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "succeeded", "failed", name="payment_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("request_hash", postgresql.CHAR(64), nullable=False),
        sa.Column("webhook_url", sa.String(2048), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_outbox_unpublished", "outbox", ["id"], postgresql_where=sa.text("published_at IS NULL")
    )


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("payments")
    postgresql.ENUM(name="payment_status").drop(op.get_bind())
    postgresql.ENUM(name="currency").drop(op.get_bind())
