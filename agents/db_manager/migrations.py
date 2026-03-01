"""Migraciones de base de datos. Idempotentes — se pueden ejecutar N veces."""
from __future__ import annotations

import aiosqlite

from core.exceptions import DBMigrationError

SCHEMA_VERSION = 1

_CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    aplicada_en DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_CLIENTES = """
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo     TEXT    NOT NULL,
    alias               TEXT,
    telefono            TEXT,
    direccion           TEXT,
    ciudad              TEXT    DEFAULT 'San Rafael',
    notas_equipamiento  TEXT,
    fecha_alta          DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_INDEX_CLIENTES = """
CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre_completo);
"""

_CREATE_HISTORIAL = """
CREATE TABLE IF NOT EXISTS historial_servicios (
    id_servicio         INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente          INTEGER NOT NULL,
    calendar_event_id   TEXT,
    fecha_servicio      DATETIME,
    tipo_trabajo        TEXT,
    descripcion         TEXT,
    estado              TEXT DEFAULT 'pendiente',
    FOREIGN KEY(id_cliente) REFERENCES clientes(id_cliente)
);
"""


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """
    Aplica migraciones de forma idempotente.

    Se puede llamar N veces sin error ni duplicados. Usa la tabla
    `schema_version` para rastrear la versión aplicada.

    Args:
        conn: Conexión activa de aiosqlite.

    Raises:
        DBMigrationError: Si ocurre un error inesperado durante la migración.
    """
    try:
        # Crear tabla de versiones primero (si no existe)
        await conn.execute(_CREATE_SCHEMA_VERSION)
        await conn.commit()

        # Verificar versión actual
        async with conn.execute(
            "SELECT MAX(version) AS max_ver FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
            current_version: int = row["max_ver"] if row["max_ver"] is not None else 0

        if current_version >= SCHEMA_VERSION:
            return  # Ya está al día

        # Aplicar schema v1
        await conn.execute(_CREATE_CLIENTES)
        await conn.execute(_CREATE_INDEX_CLIENTES)
        await conn.execute(_CREATE_HISTORIAL)
        await conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await conn.commit()

    except aiosqlite.Error as exc:
        raise DBMigrationError(f"Error al aplicar migraciones: {exc}") from exc
