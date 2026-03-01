"""Context manager async para conexiones SQLite."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite


@asynccontextmanager
async def get_db_connection(
    db_path: str = "data/agenda.db",
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Context manager async para conexiones SQLite.

    - Activa WAL mode para mejor concurrencia en escrituras.
    - Activa FOREIGN KEYS para integridad referencial.
    - Configura row_factory para acceso por nombre de columna.

    Args:
        db_path: Ruta al archivo SQLite. Usar ':memory:' para tests.
    """
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.commit()
        yield conn
