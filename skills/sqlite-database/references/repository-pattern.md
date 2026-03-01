# Repository Pattern

## Principio

Encapsular toda la lógica de acceso a datos (queries SQL) detrás de una
interfaz clara. Los consumidores (orquestador, handlers) nunca ven SQL.

## Estructura

```python
# src/db/repository.py
import aiosqlite
from typing import Optional
from src.db.models import Cliente, Evento


class Repository:
    """Repositorio unificado de acceso a datos."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Clientes ──────────────────────────────

    async def create_cliente(self, cliente: Cliente) -> int:
        cursor = await self._db.execute(
            "INSERT INTO clientes (nombre, telefono, direccion, notas) VALUES (?, ?, ?, ?)",
            (cliente.nombre, cliente.telefono, cliente.direccion, cliente.notas),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_cliente_by_id(self, cliente_id: int) -> Optional[Cliente]:
        cursor = await self._db.execute(
            "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
        )
        row = await cursor.fetchone()
        return Cliente(**dict(row)) if row else None

    async def get_cliente_by_telefono(self, telefono: str) -> Optional[Cliente]:
        cursor = await self._db.execute(
            "SELECT * FROM clientes WHERE telefono = ?", (telefono,)
        )
        row = await cursor.fetchone()
        return Cliente(**dict(row)) if row else None

    async def list_clientes(self) -> list[Cliente]:
        cursor = await self._db.execute(
            "SELECT * FROM clientes ORDER BY nombre"
        )
        rows = await cursor.fetchall()
        return [Cliente(**dict(r)) for r in rows]

    async def update_cliente(self, cliente_id: int, **kwargs) -> bool:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [cliente_id]
        cursor = await self._db.execute(
            f"UPDATE clientes SET {sets}, updated_at = datetime('now','localtime') WHERE id = ?",
            values,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    # ── Eventos ───────────────────────────────

    async def create_evento(self, evento: Evento) -> int:
        cursor = await self._db.execute(
            """INSERT INTO eventos 
            (cliente_id, google_event_id, tipo_servicio, fecha_hora, 
             duracion_minutos, estado, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (evento.cliente_id, evento.google_event_id, evento.tipo_servicio.value,
             evento.fecha_hora.isoformat(), evento.duracion_minutos,
             evento.estado.value, evento.notas),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def list_eventos_pendientes(self) -> list[Evento]:
        cursor = await self._db.execute(
            """SELECT * FROM eventos 
            WHERE estado = 'pendiente' 
            ORDER BY fecha_hora ASC"""
        )
        rows = await cursor.fetchall()
        return [Evento(**dict(r)) for r in rows]

    async def list_eventos_hoy(self) -> list[Evento]:
        cursor = await self._db.execute(
            """SELECT * FROM eventos 
            WHERE estado = 'pendiente' 
            AND date(fecha_hora) = date('now', 'localtime')
            ORDER BY fecha_hora ASC"""
        )
        rows = await cursor.fetchall()
        return [Evento(**dict(r)) for r in rows]

    async def complete_evento(self, evento_id: int, **closure_data) -> bool:
        sets = ", ".join(f"{k} = ?" for k in closure_data)
        values = list(closure_data.values()) + [evento_id]
        cursor = await self._db.execute(
            f"""UPDATE eventos 
            SET {sets}, estado = 'completado', 
                updated_at = datetime('now','localtime')
            WHERE id = ?""",
            values,
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_evento(self, evento_id: int) -> bool:
        cursor = await self._db.execute(
            "DELETE FROM eventos WHERE id = ?", (evento_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0
```

## Notas

- Usar **context manager** (`async with`) para transacciones.
- Nunca construir queries con f-strings que incluyan datos del usuario.
- Los métodos devuelven modelos Pydantic, no rows crudas.
- El repositorio es **stateful** (mantiene la conexión abierta).
