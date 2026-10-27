"""Additive schema upgrades for databases created by an earlier release.

`Base.metadata.create_all` creates missing tables but never alters existing ones, and the
project has no migration tool. Each upgrade here is idempotent, additive, and keeps existing
rows — it never drops or recreates anything.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.domain.currency import DEFAULT_CURRENCY


def ensure_schema(engine: Engine) -> None:
    columns = {c["name"] for c in inspect(engine).get_columns("plans")}
    if "budget_currency" not in columns:
        # IF NOT EXISTS keeps concurrent workers starting at once from racing (PostgreSQL).
        guard = "IF NOT EXISTS " if engine.dialect.name == "postgresql" else ""
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE plans ADD COLUMN {guard}budget_currency VARCHAR(3) "
                    f"NOT NULL DEFAULT '{DEFAULT_CURRENCY}'"
                )
            )
