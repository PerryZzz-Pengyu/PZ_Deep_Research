from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def upgrade_database(database_url: str) -> None:
    # Run Alembic in a subprocess so it is fully isolated from the parent
    # process's asyncio event loop. Using asyncio.to_thread with SQLAlchemy's
    # sync engine imported greenlet, which corrupted the ASGI lifespan
    # startup_event and prevented uvicorn from acknowledging startup completion.
    alembic = str(Path(sys.executable).parent / "alembic")
    env = {
        **os.environ,
        "DATABASE_MIGRATION_URL": database_url,
        "PYTHONPATH": str(BACKEND_ROOT),
    }
    proc = await asyncio.create_subprocess_exec(
        alembic, "upgrade", "head",
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        output = stdout.decode() if stdout else ""
        raise RuntimeError(
            f"alembic upgrade head failed (rc={proc.returncode}):\n{output}"
        )
