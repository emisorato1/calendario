"""Tests de la conexión async a SQLite."""
from __future__ import annotations

import pytest

from agents.db_manager.connection import get_db_connection


@pytest.mark.asyncio
async def test_wal_mode_activado(tmp_path):
    """WAL mode se activa correctamente en bases de datos en disco."""
    db_path = str(tmp_path / "test.db")
    async with get_db_connection(db_path) as conn:
        async with conn.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
    assert row[0] == "wal"


@pytest.mark.asyncio
async def test_foreign_keys_activados():
    """PRAGMA foreign_keys queda en ON."""
    async with get_db_connection(":memory:") as conn:
        async with conn.execute("PRAGMA foreign_keys") as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_context_manager_retorna_conexion():
    """El context manager entrega una conexión no nula."""
    async with get_db_connection(":memory:") as conn:
        assert conn is not None


@pytest.mark.asyncio
async def test_row_factory_acceso_por_nombre():
    """Las filas se recuperan como objetos con acceso por nombre de columna."""
    async with get_db_connection(":memory:") as conn:
        await conn.execute("CREATE TABLE t (id INTEGER, nombre TEXT)")
        await conn.execute("INSERT INTO t VALUES (1, 'prueba')")
        async with conn.execute("SELECT id, nombre FROM t") as cursor:
            row = await cursor.fetchone()
    assert row["nombre"] == "prueba"
    assert row["id"] == 1


@pytest.mark.asyncio
async def test_conexion_se_cierra_al_salir_del_context():
    """La conexión queda cerrada después de salir del context manager."""
    import aiosqlite
    async with get_db_connection(":memory:") as conn:
        conn_ref = conn
    # Intentar usar la conexión cerrada debería fallar
    with pytest.raises(Exception):
        await conn_ref.execute("SELECT 1")
