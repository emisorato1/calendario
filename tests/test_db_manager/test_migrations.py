"""Tests de idempotencia y correctitud de las migraciones."""
from __future__ import annotations

import pytest

from agents.db_manager.connection import get_db_connection
from agents.db_manager.migrations import SCHEMA_VERSION, run_migrations


@pytest.mark.asyncio
async def test_crea_tabla_clientes():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_crea_tabla_historial_servicios():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='historial_servicios'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_crea_tabla_schema_version():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_crea_indice_nombre_clientes():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        async with conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_clientes_nombre'"
        ) as cursor:
            row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_registra_version_en_schema_version():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        async with conn.execute("SELECT version FROM schema_version") as cursor:
            row = await cursor.fetchone()
    assert row["version"] == SCHEMA_VERSION


@pytest.mark.asyncio
async def test_idempotente_tres_ejecuciones():
    """Ejecutar 3 veces no produce errores ni duplicados."""
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        await run_migrations(conn)
        await run_migrations(conn)
        async with conn.execute(
            "SELECT COUNT(*) AS cnt FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
    assert row["cnt"] == 1


@pytest.mark.asyncio
async def test_segunda_ejecucion_no_duplica_fila_version():
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        await run_migrations(conn)
        async with conn.execute(
            "SELECT COUNT(*) AS cnt FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
    assert row["cnt"] == 1


@pytest.mark.asyncio
async def test_foreign_key_funciona_post_migracion():
    """Insertar historial sin cliente padre debe fallar (FK activado)."""
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        with pytest.raises(Exception):
            await conn.execute(
                "INSERT INTO historial_servicios (id_cliente) VALUES (9999)"
            )
            await conn.commit()
