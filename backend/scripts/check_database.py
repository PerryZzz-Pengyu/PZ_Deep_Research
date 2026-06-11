from __future__ import annotations

import asyncio

from app.config import get_settings
from app.storage.sql import SqlJobStore


async def main() -> None:
    settings = get_settings()
    store = SqlJobStore(
        settings.database_url,
        auto_create_schema=False,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout_seconds=settings.database_pool_timeout_seconds,
        pool_recycle_seconds=settings.database_pool_recycle_seconds,
    )
    try:
        connected = await store.check_connection()
        print(
            "database=ready"
            if connected
            else "database=unavailable"
        )
        print(f"backend={store.backend_name}")
    finally:
        await store.dispose()


if __name__ == "__main__":
    asyncio.run(main())
