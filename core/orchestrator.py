"""Orquestador central: conecta todos los módulos del sistema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import pytz

from agents.calendar_sync.event_builder import build_event
from agents.calendar_sync.formatter import (
    format_event_list_item,
    format_event_summary,
    format_events_list,
)
from agents.db_manager.models import Cliente, Servicio
from agents.groq_parser.schemas import Intencion, ParsedMessage
from agents.telegram_listener.keyboards import (
    CONFIRM_KEYBOARD,
    build_date_suggestion_keyboard,
    build_day_full_keyboard,
    build_event_selection_keyboard,
    build_list_submenu_keyboard,
    build_time_slot_keyboard,
)
from config.constants import (
    DURACIONES_SERVICIO,
    ESTADO_CANCELADO,
    ESTADO_PENDIENTE,
    TIMEZONE,
)
from core.logger import get_logger
from core.work_schedule import (
    calculate_free_hours,
    get_available_slots,
    get_day_schedule,
    is_day_fully_booked,
)

if TYPE_CHECKING:
    from agents.calendar_sync.client import CalendarClient
    from agents.db_manager.repository import DBRepository
    from agents.groq_parser.client import GroqClient
    from agents.groq_parser.parser import parse_message
    from config.settings import Settings

log = get_logger(__name__)
tz = pytz.timezone(TIMEZONE)


# ── Enums y Dataclasses ──────────────────────────────────────────────────────


class UserRole(str, Enum):
    admin = "admin"
    editor = "editor"


# Estados del ConversationHandler
IDLE = 0
AWAITING_CREATION_INPUT = 1
AWAITING_MISSING_DATA = 2
AWAITING_CONFIRMATION = 3
AWAITING_CANCEL_SELECTION = 4
AWAITING_CANCEL_CONFIRM = 5
AWAITING_EDIT_SELECTION = 6
AWAITING_EDIT_INSTRUCTION = 7
AWAITING_EDIT_CONFIRM = 8
AWAITING_CLIENT_NAME = 9


# Intenciones que requieren rol Admin
ADMIN_ONLY_INTENTIONS = {Intencion.agendar, Intencion.cancelar}


@dataclass
class CreationContext:
    """Contexto acumulado para el flujo de creación, incluyendo datos parciales."""

    nombre_cliente: str | None = None
    tipo_servicio: str | None = None
    fecha: date | None = None
    hora: time | None = None
    duracion_horas: float | None = None
    direccion: str | None = None
    telefono: str | None = None
    cliente_obj: Cliente | None = None
    campo_pendiente: str | None = None
    urgente: bool = False


@dataclass
class OrchestratorResponse:
    """Respuesta del orquestador para el handler de Telegram."""

    text: str
    keyboard: object | None = None  # InlineKeyboardMarkup | ReplyKeyboardMarkup
    context: dict | None = None
    next_state: int | None = None


class Orchestrator:
    """Orquestador central: conecta parser, DB, Calendar y Telegram.

    Atributos:
        settings: Configuración del sistema.
        groq_client: Cliente para Groq API.
        repository: Repositorio de datos.
        calendar_client: Cliente de Google Calendar.
    """

    def __init__(
        self,
        settings: Settings,
        groq_client: GroqClient,
        repository: DBRepository,
        calendar_client: CalendarClient,
    ) -> None:
        self._settings = settings
        self._groq = groq_client
        self._repo = repository
        self._calendar = calendar_client

    def _get_role(self, user_id: int) -> UserRole:
        """Determina el rol del usuario."""
        if self._settings.is_admin(user_id):
            return UserRole.admin
        return UserRole.editor

    async def process_message(
        self,
        text: str,
        user_id: int,
    ) -> OrchestratorResponse:
        """Entry point para mensajes de texto libre en estado IDLE.

        1. Determina el rol del usuario.
        2. Parsea la intención con el LLM.
        3. Verifica permisos.
        4. Despacha al flujo correspondiente.

        Args:
            text: Texto del mensaje del usuario.
            user_id: ID de Telegram del usuario.

        Returns:
            OrchestratorResponse con texto, teclado opcional y siguiente estado.
        """
        from agents.groq_parser.parser import parse_message

        role = self._get_role(user_id)

        parsed = await parse_message(text, self._groq)

        log.info(
            "process_message",
            user_id=user_id,
            role=role.value,
            intencion=parsed.intencion.value,
        )

        # Verificar permisos
        if parsed.intencion in ADMIN_ONLY_INTENTIONS and role != UserRole.admin:
            return OrchestratorResponse(
                text="No tenés permiso para realizar esa acción. "
                "Podés editar eventos y consultar la agenda.",
                next_state=IDLE,
            )

        # Despachar según intención
        if parsed.intencion == Intencion.agendar:
            return await self.start_creation_flow(parsed)

        if parsed.intencion == Intencion.cancelar:
            return await self._start_cancel_flow()

        if parsed.intencion == Intencion.editar:
            return await self._start_edit_flow()

        if parsed.intencion in {
            Intencion.listar_pendientes,
            Intencion.listar_historial,
            Intencion.listar_dia,
            Intencion.listar_cliente,
        }:
            return await self.resolve_list_query(parsed)

        # Intención 'otro'
        return OrchestratorResponse(
            text="No entendí bien tu pedido. Podés usar los botones del menú "
            "o escribir de forma natural qué necesitás.",
            next_state=IDLE,
        )

    async def start_creation_flow(
        self,
        parsed: ParsedMessage,
        context_data: dict | None = None,
    ) -> OrchestratorResponse:
        """Inicia o continúa el flujo de creación de un evento.

        Analiza qué campos obligatorios faltan y solicita los faltantes
        con teclados interactivos.

        Args:
            parsed: Mensaje parseado con datos del evento.
            context_data: Datos acumulados de iteraciones previas.

        Returns:
            OrchestratorResponse con solicitud de datos o resumen de confirmación.
        """
        ctx = self._build_creation_context(parsed, context_data)

        # Si falta fecha → pedir primero
        if ctx.fecha is None:
            return OrchestratorResponse(
                text="📅 *¿Para qué día querés agendar?*\n\n"
                "Elegí una fecha rápida o escribí la que necesites:",
                keyboard=build_date_suggestion_keyboard(),
                context=self._context_to_dict(ctx),
                next_state=AWAITING_MISSING_DATA,
            )

        # Verificar domingo
        if ctx.fecha.weekday() == 6:
            return OrchestratorResponse(
                text="🚫 Los domingos no hay servicio. Elegí otro día.",
                context=self._context_to_dict(ctx),
                next_state=AWAITING_MISSING_DATA,
            )

        # Si falta hora → pedir con franjas disponibles
        if ctx.hora is None:
            duracion = ctx.duracion_horas or 1.0
            eventos_dia = await self._calendar.listar_eventos_por_fecha(ctx.fecha)
            slots = get_available_slots(
                ctx.fecha,
                duracion,
                eventos_dia,
                self._settings.conflict_buffer_minutes,
            )

            is_urgent = ctx.urgente

            if not slots and not is_urgent:
                return OrchestratorResponse(
                    text=f"📅 El día {ctx.fecha.strftime('%d/%m/%Y')} "
                    "está completamente lleno.\n\n"
                    "¿Querés elegir otro día o es urgente?",
                    keyboard=build_day_full_keyboard(ctx.fecha),
                    context=self._context_to_dict(ctx),
                    next_state=AWAITING_MISSING_DATA,
                )

            ctx.campo_pendiente = "hora"
            keyboard = build_time_slot_keyboard(ctx.fecha, duracion, self._settings, eventos_dia)

            return OrchestratorResponse(
                text="🕒 *¿A qué hora querés agendar?*\n\nHorarios disponibles:",
                keyboard=keyboard,
                context=self._context_to_dict(ctx),
                next_state=AWAITING_MISSING_DATA,
            )

        # Todo completo → buscar/crear cliente y mostrar resumen
        return await self._build_confirmation(ctx)

    async def complete_missing_field(
        self,
        field_name: str,
        value: str,
        context_data: dict,
    ) -> OrchestratorResponse:
        """Recibe el valor del campo faltante y continúa el flujo de creación.

        Args:
            field_name: Nombre del campo ("fecha" o "hora").
            value: Valor proporcionado por el usuario.
            context_data: Datos acumulados del contexto.

        Returns:
            OrchestratorResponse con siguiente solicitud o resumen.
        """
        raw = {k: v for k, v in context_data.items() if k in CreationContext.__dataclass_fields__}
        # Convertir strings serializados a tipos nativos
        if isinstance(raw.get("fecha"), str):
            raw["fecha"] = date.fromisoformat(raw["fecha"])
        if isinstance(raw.get("hora"), str):
            parts = raw["hora"].split(":")
            raw["hora"] = time(int(parts[0]), int(parts[1]))
        ctx = CreationContext(**raw)

        if field_name == "fecha":
            try:
                ctx.fecha = date.fromisoformat(value)
            except ValueError:
                # Intentar parsear con LLM como texto libre
                from agents.groq_parser.parser import parse_message

                parsed = await parse_message(f"agendar para {value}", self._groq)
                ctx.fecha = parsed.fecha

        elif field_name == "hora":
            try:
                parts = value.split(":")
                ctx.hora = time(int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                # Intentar parsear con LLM como texto libre
                from agents.groq_parser.parser import parse_message

                parsed = await parse_message(f"agendar a las {value}", self._groq)
                ctx.hora = parsed.hora

        # Reconstruir ParsedMessage para continuar
        parsed = self._context_to_parsed(ctx)
        return await self.start_creation_flow(parsed, self._context_to_dict(ctx))

    async def check_day_capacity(
        self,
        fecha: date,
        duracion_horas: float,
    ) -> tuple[bool, float]:
        """Verifica si el día tiene horas laborales suficientes.

        Args:
            fecha: Fecha a verificar.
            duracion_horas: Duración del servicio en horas.

        Returns:
            Tupla (tiene_capacidad, horas_libres_restantes).
        """
        schedule = get_day_schedule(fecha)
        if schedule is None:
            return (False, 0.0)

        eventos = await self._calendar.listar_eventos_por_fecha(fecha)
        free = calculate_free_hours(fecha, eventos)
        return (free >= duracion_horas, free)

    async def confirm_event(self, context: CreationContext) -> OrchestratorResponse:
        """Post-confirmación: crea evento en Calendar y registra en DB.

        Args:
            context: Contexto completo de la creación.

        Returns:
            OrchestratorResponse con confirmación y link al evento.
        """
        cliente = context.cliente_obj
        if cliente is None:
            return OrchestratorResponse(
                text="❌ Error interno: no se encontró el cliente.",
                next_state=IDLE,
            )

        parsed = self._context_to_parsed(context)
        evento_dict = build_event(parsed, cliente)

        try:
            resultado = await self._calendar.crear_evento(evento_dict)
        except Exception as exc:
            log.error("error_crear_evento_calendar", error=str(exc))
            return OrchestratorResponse(
                text="❌ Error al crear el evento en Google Calendar. Intentá de nuevo más tarde.",
                next_state=IDLE,
            )

        # Registrar servicio en DB
        try:
            servicio = Servicio(
                id_cliente=cliente.id_cliente,
                calendar_event_id=resultado.get("id"),
                fecha_servicio=datetime.combine(context.fecha, context.hora),
                tipo_trabajo=context.tipo_servicio,
                descripcion=f"Creado vía IA",
                estado=ESTADO_PENDIENTE,
            )
            await self._repo.registrar_servicio(servicio)
        except Exception as exc:
            log.error("error_registrar_servicio_db", error=str(exc))

        html_link = resultado.get("htmlLink", "")
        nombre = cliente.nombre_completo
        tipo = (context.tipo_servicio or "servicio").capitalize()

        return OrchestratorResponse(
            text=f"✅ Evento creado exitosamente.\n"
            f"📅 {tipo} para {nombre}\n"
            f"🔗 [Ver en Calendar]({html_link})",
            next_state=IDLE,
        )

    async def get_upcoming_events_for_selection(self) -> tuple[list[dict], str]:
        """Lista eventos próximos para selección en flujos de edición/cancelación.

        Returns:
            Tupla (lista_eventos, texto_formateado).
        """
        eventos = await self._calendar.listar_proximos_eventos(n=self._settings.max_events_list)

        if not eventos:
            return ([], "No hay eventos próximos programados.")

        lines = ["📅 *Eventos próximos:*\n"]
        for i, evt in enumerate(eventos, 1):
            lines.append(format_event_list_item(evt, i))

        text = "\n".join(lines)
        text += "\n\n¿Cuál evento querés seleccionar?"

        return (eventos, text)

    async def resolve_list_query(self, parsed: ParsedMessage) -> OrchestratorResponse:
        """Resuelve cualquier tipo de intención de listado delegando a métodos dedicados.

        Args:
            parsed: Mensaje parseado con intención de listado.

        Returns:
            OrchestratorResponse con la lista formateada.
        """
        if parsed.intencion == Intencion.listar_pendientes:
            text = await self.listar_pendientes()
            return OrchestratorResponse(text=text, next_state=IDLE)

        if parsed.intencion == Intencion.listar_dia:
            fecha = parsed.fecha_consulta or parsed.fecha or date.today()
            text = await self.listar_por_dia(fecha)
            return OrchestratorResponse(text=text, next_state=IDLE)

        if parsed.intencion == Intencion.listar_cliente:
            nombre = parsed.cliente_consulta or parsed.nombre_cliente
            if not nombre:
                return OrchestratorResponse(
                    text="👤 ¿De qué cliente querés ver los eventos? Escribí el nombre:",
                    next_state=AWAITING_CLIENT_NAME,
                )
            text = await self.listar_por_cliente(nombre)
            return OrchestratorResponse(text=text, next_state=IDLE)

        if parsed.intencion == Intencion.listar_historial:
            text = await self.listar_historial()
            return OrchestratorResponse(text=text, next_state=IDLE)

        return OrchestratorResponse(
            text="No pude determinar qué listado necesitás.",
            next_state=IDLE,
        )

    async def listar_pendientes(self) -> str:
        """Eventos futuros desde ahora hasta 30 días adelante.

        Returns:
            Texto formateado con la lista de eventos pendientes.
        """
        now = datetime.now(tz)
        time_max = now + timedelta(days=30)
        eventos = await self._calendar.listar_eventos(
            time_min=now,
            time_max=time_max,
            max_results=self._settings.max_events_list,
        )
        return format_events_list(eventos, "Eventos pendientes")

    async def listar_historial(self, dias: int = 30) -> str:
        """Eventos pasados de los últimos N días.

        Args:
            dias: Cantidad de días hacia atrás (default 30).

        Returns:
            Texto formateado con el historial de eventos.
        """
        now = datetime.now(tz)
        time_min = now - timedelta(days=dias)
        eventos = await self._calendar.listar_eventos(
            time_min=time_min,
            time_max=now,
            max_results=50,
        )
        return format_events_list(eventos, "Historial de eventos")

    async def listar_por_dia(self, fecha: date) -> str:
        """Todos los eventos de una fecha específica.

        Incluye indicador de día completo si no quedan franjas disponibles.

        Args:
            fecha: Fecha a consultar.

        Returns:
            Texto formateado con los eventos del día.
        """
        eventos = await self._calendar.listar_eventos_por_fecha(fecha)
        dia_str = fecha.strftime("%d/%m/%Y")

        # Verificar si el día está completo
        dia_completo = False
        if eventos:
            dia_completo = is_day_fully_booked(
                fecha, 1.0, eventos, self._settings.conflict_buffer_minutes
            )

        text = format_events_list(eventos, f"Eventos del {dia_str}")
        if dia_completo:
            text += "\n\n⚠️ *Día completo* — No quedan franjas disponibles."
        return text

    async def listar_por_cliente(self, nombre_cliente: str) -> str:
        """Busca eventos de un cliente usando fuzzy match.

        Separa los resultados en pendientes (futuros) e historial (pasados).

        Args:
            nombre_cliente: Nombre del cliente a buscar.

        Returns:
            Texto formateado con pendientes + historial del cliente.
        """
        # Fuzzy match en DB para nombre correcto
        cliente = await self._repo.buscar_cliente_fuzzy(
            nombre_cliente, self._settings.fuzzy_match_threshold
        )
        nombre_buscar = cliente.nombre_completo if cliente else nombre_cliente

        # Buscar eventos en Calendar
        eventos = await self._calendar.buscar_eventos_por_cliente(nombre_buscar)

        if not eventos:
            return f"👤 *Turnos de {nombre_buscar}:*\n\nNo se encontraron eventos."

        # Separar pendientes vs historial
        now = datetime.now(tz)
        pendientes = []
        historial = []
        for evt in eventos:
            start_str = evt.get("start", {}).get("dateTime", "")
            if start_str:
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is None:
                    start_dt = tz.localize(start_dt)
                if start_dt >= now:
                    pendientes.append(evt)
                else:
                    historial.append(evt)
            else:
                pendientes.append(evt)

        lines = [f"👤 *Turnos de {nombre_buscar}:*"]

        if pendientes:
            lines.append("\n*Próximos:*")
            for i, evt in enumerate(pendientes, 1):
                lines.append(f"📌 {format_event_list_item(evt, i)}")
        else:
            lines.append("\n*Próximos:*\nNo hay turnos próximos.")

        if historial:
            lines.append("\n*Historial:*")
            for i, evt in enumerate(historial, 1):
                lines.append(f"✅ {format_event_list_item(evt, i)}")
        else:
            lines.append("\n*Historial:*\nNo hay turnos anteriores.")

        return "\n".join(lines)

    # ── Cancelación y Edición ────────────────────────────────────────────────

    async def confirm_cancel(self, event_id: str) -> OrchestratorResponse:
        """Elimina evento del Calendar y actualiza estado en DB a 'cancelado'.

        Args:
            event_id: ID del evento en Google Calendar.

        Returns:
            OrchestratorResponse con confirmación o error.
        """
        try:
            await self._calendar.eliminar_evento(event_id)
        except Exception as exc:
            log.error("error_cancelar_evento_calendar", error=str(exc))
            return OrchestratorResponse(
                text="❌ Error al cancelar el evento. Intentá de nuevo.",
                next_state=IDLE,
            )

        # Actualizar estado en DB
        try:
            servicio = await self._repo.buscar_servicio_por_event_id(event_id)
            if servicio and servicio.id_servicio is not None:
                await self._repo.actualizar_estado_servicio(servicio.id_servicio, ESTADO_CANCELADO)
        except Exception as exc:
            log.warning("error_actualizar_estado_db_cancel", error=str(exc))

        return OrchestratorResponse(
            text="✅ Evento cancelado exitosamente.",
            next_state=IDLE,
        )

    async def parse_and_preview_edit(
        self,
        instruccion: str,
        evento_actual: dict,
    ) -> OrchestratorResponse:
        """Parsea instrucción de edición y genera preview de cambios.

        1. Llama a groq_parser.parse_edit_instruction.
        2. Genera build_patch para obtener el dict de cambios.
        3. Construye resumen legible + teclado de confirmación.

        Args:
            instruccion: Texto libre con la instrucción de edición.
            evento_actual: Dict del evento actual de Google Calendar.

        Returns:
            OrchestratorResponse con preview y patch en context.
        """
        from agents.calendar_sync.event_builder import build_patch
        from agents.groq_parser.parser import parse_edit_instruction

        edit = await parse_edit_instruction(
            instruccion=instruccion,
            evento_actual=evento_actual,
            client=self._groq,
        )

        # Buscar cliente para build_patch
        summary = evento_actual.get("summary", "")
        nombre_cliente = summary.split(" - ")[0] if " - " in summary else summary
        cliente = await self._repo.buscar_cliente_fuzzy(
            nombre_cliente, self._settings.fuzzy_match_threshold
        )
        if not cliente:
            cliente = Cliente(nombre_completo=nombre_cliente)

        patch = build_patch(edit, evento_actual, cliente)

        # Construir preview legible
        cambios = [
            f"• {k.replace('_', ' ').title()}: {v}"
            for k, v in edit.model_dump().items()
            if v is not None
        ]
        preview = "\n".join(cambios)

        return OrchestratorResponse(
            text=f"✏️ *Cambios a aplicar:*\n\n{preview}\n\n¿Confirmar?",
            keyboard=CONFIRM_KEYBOARD,
            context={
                "edit_instruction": edit.model_dump(mode="json"),
                "patch": patch,
            },
            next_state=AWAITING_EDIT_CONFIRM,
        )

    async def confirm_edit(
        self,
        event_id: str,
        patch: dict,
        nuevo_tipo_trabajo: str | None = None,
    ) -> OrchestratorResponse:
        """Aplica PATCH al Calendar y actualiza DB si cambió el tipo de servicio.

        Args:
            event_id: ID del evento en Google Calendar.
            patch: Dict con los campos a modificar.
            nuevo_tipo_trabajo: Nuevo tipo de servicio si cambió (ej: "instalacion").

        Returns:
            OrchestratorResponse con confirmación o error.
        """
        try:
            resultado = await self._calendar.actualizar_evento(event_id, patch)
        except Exception as exc:
            log.error("error_aplicar_edicion_calendar", error=str(exc))
            return OrchestratorResponse(
                text="❌ Error al aplicar los cambios. Intentá de nuevo.",
                next_state=IDLE,
            )

        # Si cambió tipo de servicio, actualizar tipo_trabajo en DB
        if nuevo_tipo_trabajo:
            try:
                servicio = await self._repo.buscar_servicio_por_event_id(event_id)
                if servicio and servicio.id_servicio is not None:
                    await self._repo.actualizar_tipo_trabajo(
                        servicio.id_servicio, nuevo_tipo_trabajo
                    )
            except Exception as exc:
                log.warning("error_actualizar_db_edit", error=str(exc))

        html_link = resultado.get("htmlLink", "")
        text = "✅ Evento actualizado exitosamente."
        if html_link:
            text += f"\n🔗 [Ver en Calendar]({html_link})"

        return OrchestratorResponse(
            text=text,
            next_state=IDLE,
        )

    # ── Flujos internos ──────────────────────────────────────────────────────

    async def _start_cancel_flow(self) -> OrchestratorResponse:
        """Inicia el flujo de cancelación mostrando eventos próximos."""
        eventos, text = await self.get_upcoming_events_for_selection()
        if not eventos:
            return OrchestratorResponse(text=text, next_state=IDLE)

        return OrchestratorResponse(
            text=text,
            keyboard=build_event_selection_keyboard(eventos),
            context={"eventos_seleccion": eventos},
            next_state=AWAITING_CANCEL_SELECTION,
        )

    async def _start_edit_flow(self) -> OrchestratorResponse:
        """Inicia el flujo de edición mostrando eventos próximos."""
        eventos, text = await self.get_upcoming_events_for_selection()
        if not eventos:
            return OrchestratorResponse(text=text, next_state=IDLE)

        return OrchestratorResponse(
            text=text,
            keyboard=build_event_selection_keyboard(eventos),
            context={"eventos_seleccion": eventos},
            next_state=AWAITING_EDIT_SELECTION,
        )

    async def _build_confirmation(self, ctx: CreationContext) -> OrchestratorResponse:
        """Busca/crea cliente y construye resumen de confirmación."""
        # Buscar cliente en DB
        if ctx.nombre_cliente:
            cliente = await self._repo.buscar_cliente_fuzzy(
                ctx.nombre_cliente,
                self._settings.fuzzy_match_threshold,
            )
            if cliente is None:
                # Crear cliente nuevo
                cliente = await self._repo.crear_cliente(
                    {
                        "nombre_completo": ctx.nombre_cliente,
                        "telefono": ctx.telefono,
                        "direccion": ctx.direccion,
                    }
                )
            ctx.cliente_obj = cliente
        else:
            # Sin nombre de cliente, crear uno genérico
            ctx.cliente_obj = await self._repo.crear_cliente(
                {
                    "nombre_completo": "Cliente sin nombre",
                }
            )

        parsed = self._context_to_parsed(ctx)
        evento_dict = build_event(parsed, ctx.cliente_obj)
        resumen = format_event_summary(evento_dict)

        return OrchestratorResponse(
            text=f"📋 *Resumen del evento*\n\n{resumen}\n\n¿Confirmar este evento?",
            keyboard=CONFIRM_KEYBOARD,
            context=self._context_to_dict(ctx),
            next_state=AWAITING_CONFIRMATION,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_creation_context(
        self,
        parsed: ParsedMessage,
        context_data: dict | None = None,
    ) -> CreationContext:
        """Construye un CreationContext combinando parsed y context_data."""
        ctx = CreationContext()

        # Primero cargar context_data previo si existe
        if context_data:
            for k, v in context_data.items():
                if k in CreationContext.__dataclass_fields__ and v is not None:
                    if k == "fecha" and isinstance(v, str):
                        v = date.fromisoformat(v)
                    elif k == "hora" and isinstance(v, str):
                        parts = v.split(":")
                        v = time(int(parts[0]), int(parts[1]))
                    setattr(ctx, k, v)

        # Sobrescribir con datos del parsed (solo si no-None)
        if parsed.nombre_cliente:
            ctx.nombre_cliente = parsed.nombre_cliente
        if parsed.tipo_servicio:
            ctx.tipo_servicio = parsed.tipo_servicio.value
        if parsed.fecha:
            ctx.fecha = parsed.fecha
        if parsed.hora:
            ctx.hora = parsed.hora
        if parsed.duracion_estimada_horas:
            ctx.duracion_horas = parsed.duracion_estimada_horas
        if parsed.direccion:
            ctx.direccion = parsed.direccion
        if parsed.telefono:
            ctx.telefono = parsed.telefono
        if parsed.urgente:
            ctx.urgente = True

        # Inferir duración si no la tenemos
        if ctx.duracion_horas is None and ctx.tipo_servicio:
            ctx.duracion_horas = DURACIONES_SERVICIO.get(ctx.tipo_servicio, 1.0)

        return ctx

    def _context_to_dict(self, ctx: CreationContext) -> dict:
        """Serializa CreationContext a dict para user_data."""
        return {
            "nombre_cliente": ctx.nombre_cliente,
            "tipo_servicio": ctx.tipo_servicio,
            "fecha": ctx.fecha.isoformat() if ctx.fecha else None,
            "hora": ctx.hora.strftime("%H:%M") if ctx.hora else None,
            "duracion_horas": ctx.duracion_horas,
            "direccion": ctx.direccion,
            "telefono": ctx.telefono,
            "campo_pendiente": ctx.campo_pendiente,
            "urgente": ctx.urgente,
            "cliente_id": ctx.cliente_obj.id_cliente if ctx.cliente_obj else None,
        }

    def _context_to_parsed(self, ctx: CreationContext) -> ParsedMessage:
        """Reconstruye un ParsedMessage a partir del CreationContext."""
        from agents.groq_parser.schemas import TipoServicio

        tipo = None
        if ctx.tipo_servicio:
            try:
                tipo = TipoServicio(ctx.tipo_servicio)
            except ValueError:
                tipo = TipoServicio.otro

        return ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente=ctx.nombre_cliente,
            tipo_servicio=tipo,
            fecha=ctx.fecha,
            hora=ctx.hora,
            duracion_estimada_horas=ctx.duracion_horas,
            direccion=ctx.direccion,
            telefono=ctx.telefono,
            urgente=ctx.urgente,
        )
