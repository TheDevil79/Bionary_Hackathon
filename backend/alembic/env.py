"""
Alembic environment configuration for EvidenceLens.

- Uses the DATABASE_URL environment variable (via app.core.config.settings).
- Runs in ONLINE mode only (async migrations not supported by Alembic;
  we use the synchronous driver for migrations).
- Imports all models so Alembic can detect schema changes automatically.
"""

from __future__ import annotations

import sys
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Path setup ────────────────────────────────────────────────────────────────
# Ensure backend/ is on sys.path so we can import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── App imports ───────────────────────────────────────────────────────────────
from app.core.config import settings
from app.core.database import Base

# Import all models so Alembic sees them in metadata
import app.models.evidence  # noqa: F401

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the DATABASE_URL from environment (synchronous driver for migrations)
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

target_metadata = Base.metadata


# ── Migration runner ──────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
