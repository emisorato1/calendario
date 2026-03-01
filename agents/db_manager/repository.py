"""Repositorio de datos: CRUD de clientes y servicios con fuzzy search."""

from __future__ import annotations

from typing import Optional

import aiosqlite
from thefuzz import fuzz, process

from agents.db_manager.cache import ClienteCache
from agents.db_manager.models import Cliente, Servicio
from core.exceptions import ClienteNoEncontradoError
from core.logger import get_logger

logger = get_logger(__name__)


class DBRepository:
    """
    Repositorio de acceso a datos para clientes y servicios.

    Usa fuzzy search con `thefuzz` para tolerar variantes de nombres.
    Incluye cache LRU con TTL de 5 minutos para búsquedas frecuentes.
    """

    def __init__(
        self,
        conn: aiosqlite.Connection,
        cache: Optional[ClienteCache] = None,
    ) -> None:
        self._conn = conn
        self._cache = cache if cache is not None else ClienteCache()

    # ── Clientes ──────────────────────────────────────────────────────────────

    async def buscar_cliente_fuzzy(
        self,
        nombre: str,
        threshold: int = 75,
    ) -> Optional[Cliente]:
        """
        Busca un cliente por nombre con tolerancia a errores tipográficos.

        Args:
            nombre: Nombre a buscar (puede tener typos).
            threshold: Porcentaje mínimo de similitud (0-100).

        Returns:
            El cliente con mayor similitud si supera el threshold, o None.
        """
        # Revisar caché primero
        cached = self._cache.get(nombre)
        if cached is not None:
            logger.debug("cache_hit", query=nombre)
            return cached

        async with self._conn.execute(
            "SELECT id_cliente, nombre_completo, alias, telefono, "
            "direccion, ciudad, notas_equipamiento, fecha_alta FROM clientes"
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            return None

        nombres_map: dict[str, aiosqlite.Row] = {row["nombre_completo"]: row for row in rows}

        result = process.extractOne(
            nombre,
            nombres_map.keys(),
            scorer=fuzz.token_sort_ratio,
        )

        if result is None or result[1] < threshold:
            logger.debug("fuzzy_no_match", query=nombre, best_score=result[1] if result else 0)
            return None

        best_name, score, *_ = result
        logger.debug("fuzzy_match_found", query=nombre, match=best_name, score=score)

        cliente = self._row_to_cliente(nombres_map[best_name])
        self._cache.set(nombre, cliente)
        return cliente

    async def crear_cliente(self, datos: dict) -> Cliente:
        """
        Inserta un nuevo cliente y retorna el objeto creado.

        Args:
            datos: Dict con campos del cliente. 'nombre_completo' es requerido.
        """
        cursor = await self._conn.execute(
            """
            INSERT INTO clientes
                (nombre_completo, alias, telefono, direccion, ciudad, notas_equipamiento)
            VALUES
                (:nombre_completo, :alias, :telefono, :direccion, :ciudad, :notas_equipamiento)
            """,
            {
                "nombre_completo": datos["nombre_completo"],
                "alias": datos.get("alias"),
                "telefono": datos.get("telefono"),
                "direccion": datos.get("direccion"),
                "ciudad": datos.get("ciudad", "San Rafael"),
                "notas_equipamiento": datos.get("notas_equipamiento"),
            },
        )
        await self._conn.commit()
        cliente_id = cursor.lastrowid
        self._cache.clear()
        logger.info("cliente_creado", id_cliente=cliente_id, nombre=datos["nombre_completo"])
        return await self._get_cliente_by_id(cliente_id)

    async def actualizar_cliente(self, id_cliente: int, cambios: dict) -> Cliente:
        """
        Actualiza campos parciales de un cliente.

        Args:
            id_cliente: ID del cliente a actualizar.
            cambios: Dict con los campos a modificar.
        """
        if not cambios:
            return await self._get_cliente_by_id(id_cliente)

        set_clause = ", ".join(f"{k} = :{k}" for k in cambios)
        cambios["id_cliente"] = id_cliente
        await self._conn.execute(
            f"UPDATE clientes SET {set_clause} WHERE id_cliente = :id_cliente",
            cambios,
        )
        await self._conn.commit()
        self._cache.clear()
        logger.info("cliente_actualizado", id_cliente=id_cliente, campos=list(cambios.keys()))
        return await self._get_cliente_by_id(id_cliente)

    async def listar_clientes(self, limit: int = 10) -> list[Cliente]:
        """
        Retorna los últimos N clientes ordenados por actividad reciente.

        Args:
            limit: Máximo de clientes a retornar.
        """
        async with self._conn.execute(
            """
            SELECT c.id_cliente, c.nombre_completo, c.alias, c.telefono,
                   c.direccion, c.ciudad, c.notas_equipamiento, c.fecha_alta
            FROM clientes c
            LEFT JOIN historial_servicios h ON c.id_cliente = h.id_cliente
            GROUP BY c.id_cliente
            ORDER BY MAX(COALESCE(h.fecha_servicio, c.fecha_alta)) DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_cliente(row) for row in rows]

    # ── Servicios ─────────────────────────────────────────────────────────────

    async def registrar_servicio(self, servicio: Servicio) -> int:
        """
        Inserta un servicio en el historial y retorna su ID.

        Args:
            servicio: Objeto Servicio a registrar.
        """
        cursor = await self._conn.execute(
            """
            INSERT INTO historial_servicios
                (id_cliente, calendar_event_id, fecha_servicio,
                 tipo_trabajo, descripcion, estado)
            VALUES
                (:id_cliente, :calendar_event_id, :fecha_servicio,
                 :tipo_trabajo, :descripcion, :estado)
            """,
            {
                "id_cliente": servicio.id_cliente,
                "calendar_event_id": servicio.calendar_event_id,
                "fecha_servicio": servicio.fecha_servicio,
                "tipo_trabajo": servicio.tipo_trabajo,
                "descripcion": servicio.descripcion,
                "estado": servicio.estado,
            },
        )
        await self._conn.commit()
        logger.info(
            "servicio_registrado", id_servicio=cursor.lastrowid, id_cliente=servicio.id_cliente
        )
        return cursor.lastrowid

    async def buscar_servicio_por_event_id(self, calendar_event_id: str) -> Optional[Servicio]:
        """
        Busca un servicio en el historial por su calendar_event_id.

        Args:
            calendar_event_id: ID del evento en Google Calendar.

        Returns:
            El Servicio encontrado o None si no existe.
        """
        async with self._conn.execute(
            """
            SELECT id_servicio, id_cliente, calendar_event_id, fecha_servicio,
                   tipo_trabajo, descripcion, estado
            FROM historial_servicios
            WHERE calendar_event_id = ?
            """,
            (calendar_event_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return Servicio(
            id_servicio=row["id_servicio"],
            id_cliente=row["id_cliente"],
            calendar_event_id=row["calendar_event_id"],
            fecha_servicio=row["fecha_servicio"],
            tipo_trabajo=row["tipo_trabajo"],
            descripcion=row["descripcion"],
            estado=row["estado"],
        )

    async def actualizar_estado_servicio(self, id_servicio: int, estado: str) -> None:
        """
        Actualiza el estado de un servicio (ej: 'cancelado', 'realizado').

        Args:
            id_servicio: ID del servicio a actualizar.
            estado: Nuevo estado ('pendiente', 'realizado', 'cancelado').
        """
        await self._conn.execute(
            "UPDATE historial_servicios SET estado = ? WHERE id_servicio = ?",
            (estado, id_servicio),
        )
        await self._conn.commit()
        logger.info("servicio_estado_actualizado", id_servicio=id_servicio, estado=estado)

    # ── Helpers privados ──────────────────────────────────────────────────────

    async def _get_cliente_by_id(self, id_cliente: int) -> Cliente:
        """Recupera un cliente por su ID. Lanza ClienteNoEncontradoError si no existe."""
        async with self._conn.execute(
            """
            SELECT id_cliente, nombre_completo, alias, telefono,
                   direccion, ciudad, notas_equipamiento, fecha_alta
            FROM clientes WHERE id_cliente = ?
            """,
            (id_cliente,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            raise ClienteNoEncontradoError(f"Cliente con ID {id_cliente} no encontrado")

        return self._row_to_cliente(row)

    @staticmethod
    def _row_to_cliente(row: aiosqlite.Row) -> Cliente:
        """Convierte una fila de DB en un dataclass Cliente."""
        return Cliente(
            id_cliente=row["id_cliente"],
            nombre_completo=row["nombre_completo"],
            alias=row["alias"],
            telefono=row["telefono"],
            direccion=row["direccion"],
            ciudad=row["ciudad"] or "San Rafael",
            notas_equipamiento=row["notas_equipamiento"],
            fecha_alta=row["fecha_alta"],
        )
