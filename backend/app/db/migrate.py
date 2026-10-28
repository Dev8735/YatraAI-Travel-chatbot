"""Programmatic Alembic upgrade, used at startup and by `python -m app.db.migrate`."""

from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR, get_settings


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url or get_settings().database_url)
    return cfg


def upgrade_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


async def upgrade_head_async(database_url: str | None = None) -> None:
    # env.py drives its own event loop, so run it in a worker thread.
    await asyncio.to_thread(upgrade_head, database_url)


if __name__ == "__main__":
    upgrade_head()
    print("Database migrated to head.")
