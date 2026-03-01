"""Wrapper async sobre la API de Google Calendar."""

from __future__ import annotations

import asyncio
import time as time_mod
from datetime import date, datetime
from typing import Any

import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from config.constants import TIMEZONE
from core.exceptions import CalendarError, EventoNoEncontradoError
from core.logger import get_logger

log = get_logger(__name__)

tz = pytz.timezone(TIMEZONE)


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Determina si un HttpError es retryable (429, 500, 503)."""
    if isinstance(exc, HttpError):
        return exc.resp.status in (429, 500, 503)
    return False


class CalendarClient:
    """Cliente async para la API de Google Calendar.

    Usa asyncio.to_thread() para envolver las llamadas sync de googleapiclient.

    Args:
        credentials: Credenciales de Service Account autenticadas.
        calendar_id: ID del calendario de Google.
        timeout: Timeout en segundos para cada operación (default 15).
    """

    def __init__(
        self,
        credentials: Credentials,
        calendar_id: str,
        timeout: int = 15,
    ) -> None:
        self._credentials = credentials
        self._calendar_id = calendar_id
        self._timeout = timeout
        self._service = build("calendar", "v3", credentials=credentials)

    @retry(
        retry=retry_if_exception(_is_retryable_http_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _execute(self, request: Any) -> Any:
        """Ejecuta un request de Google API en un thread, con reintentos.

        Args:
            request: Objeto request de googleapiclient.

        Returns:
            Respuesta de la API.

        Raises:
            CalendarError: Si la operación falla después de reintentos.
        """
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(request.execute),
                timeout=self._timeout,
            )
        except HttpError:
            raise
        except asyncio.TimeoutError as exc:
            raise CalendarError(f"Timeout ({self._timeout}s) al ejecutar operación") from exc
        except Exception as exc:
            raise CalendarError(f"Error inesperado: {exc}") from exc
        return result

    async def crear_evento(self, evento: dict) -> dict:
        """Crea un evento y retorna el objeto completo con ID asignado.

        Args:
            evento: Dict con datos del evento para la API.

        Returns:
            Dict del evento creado con ID y htmlLink.
        """
        start = time_mod.monotonic()
        request = self._service.events().insert(
            calendarId=self._calendar_id,
            body=evento,
        )
        result = await self._execute(request)
        elapsed = time_mod.monotonic() - start
        log.info(
            "evento_creado",
            event_id=result.get("id"),
            duracion_ms=round(elapsed * 1000),
        )
        return result

    async def actualizar_evento(self, event_id: str, cambios: dict) -> dict:
        """PATCH parcial de un evento. Solo modifica los campos provistos.

        Args:
            event_id: ID del evento a modificar.
            cambios: Dict con solo los campos a cambiar.

        Returns:
            Dict del evento actualizado.
        """
        start = time_mod.monotonic()
        request = self._service.events().patch(
            calendarId=self._calendar_id,
            eventId=event_id,
            body=cambios,
        )
        try:
            result = await self._execute(request)
        except HttpError as exc:
            if exc.resp.status == 404:
                raise EventoNoEncontradoError(f"Evento {event_id} no encontrado") from exc
            raise
        elapsed = time_mod.monotonic() - start
        log.info(
            "evento_actualizado",
            event_id=event_id,
            duracion_ms=round(elapsed * 1000),
        )
        return result

    async def eliminar_evento(self, event_id: str) -> None:
        """Elimina un evento por ID.

        Args:
            event_id: ID del evento a eliminar.

        Raises:
            EventoNoEncontradoError: Si el evento no existe.
        """
        start = time_mod.monotonic()
        request = self._service.events().delete(
            calendarId=self._calendar_id,
            eventId=event_id,
        )
        try:
            await self._execute(request)
        except HttpError as exc:
            if exc.resp.status == 404:
                raise EventoNoEncontradoError(f"Evento {event_id} no encontrado") from exc
            raise
        elapsed = time_mod.monotonic() - start
        log.info(
            "evento_eliminado",
            event_id=event_id,
            duracion_ms=round(elapsed * 1000),
        )

    async def listar_eventos(
        self,
        time_min: datetime,
        time_max: datetime,
        max_results: int = 10,
    ) -> list[dict]:
        """Lista eventos en un rango de fechas, ordenados por inicio.

        Args:
            time_min: Inicio del rango.
            time_max: Fin del rango.
            max_results: Máximo de resultados (default 10).

        Returns:
            Lista de dicts de eventos.
        """
        start = time_mod.monotonic()
        request = self._service.events().list(
            calendarId=self._calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        result = await self._execute(request)
        elapsed = time_mod.monotonic() - start
        eventos = result.get("items", [])
        log.info(
            "eventos_listados",
            rango=f"{time_min.isoformat()} - {time_max.isoformat()}",
            total=len(eventos),
            duracion_ms=round(elapsed * 1000),
        )
        return eventos

    async def listar_proximos_eventos(self, n: int = 10) -> list[dict]:
        """Retorna los próximos N eventos desde ahora.

        Args:
            n: Cantidad máxima de eventos a retornar.

        Returns:
            Lista de dicts de eventos ordenados por fecha.
        """
        now = datetime.now(tz)
        start = time_mod.monotonic()
        request = self._service.events().list(
            calendarId=self._calendar_id,
            timeMin=now.isoformat(),
            maxResults=n,
            singleEvents=True,
            orderBy="startTime",
        )
        result = await self._execute(request)
        elapsed = time_mod.monotonic() - start
        eventos = result.get("items", [])
        log.info(
            "proximos_eventos_listados",
            total=len(eventos),
            duracion_ms=round(elapsed * 1000),
        )
        return eventos

    async def listar_eventos_por_fecha(self, fecha: date) -> list[dict]:
        """Todos los eventos de un día específico.

        Args:
            fecha: Fecha del día a consultar.

        Returns:
            Lista de dicts de eventos del día.
        """
        time_min = tz.localize(datetime.combine(fecha, datetime.min.time()))
        time_max = tz.localize(datetime.combine(fecha, datetime.max.time().replace(microsecond=0)))
        return await self.listar_eventos(
            time_min=time_min,
            time_max=time_max,
            max_results=50,
        )

    async def buscar_eventos_por_cliente(
        self,
        nombre_cliente: str,
    ) -> list[dict]:
        """Busca eventos cuyo título contenga el nombre del cliente.

        Busca eventos pasados (90 días atrás) y futuros (90 días adelante)
        para poder separar en pendientes e historial.

        Args:
            nombre_cliente: Nombre del cliente a buscar.

        Returns:
            Lista de dicts de eventos que coinciden.
        """
        now = datetime.now(tz)
        from datetime import timedelta

        time_min = now - timedelta(days=90)
        time_max = now + timedelta(days=90)
        start = time_mod.monotonic()
        request = self._service.events().list(
            calendarId=self._calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
            q=nombre_cliente,
        )
        result = await self._execute(request)
        elapsed = time_mod.monotonic() - start
        eventos = result.get("items", [])
        log.info(
            "busqueda_por_cliente",
            cliente=nombre_cliente,
            total=len(eventos),
            duracion_ms=round(elapsed * 1000),
        )
        return eventos
