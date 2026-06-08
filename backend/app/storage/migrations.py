from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _upgrade_database(database_url: str) -> None:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


async def upgrade_database(database_url: str) -> None:
    await asyncio.to_thread(_upgrade_database, database_url)
