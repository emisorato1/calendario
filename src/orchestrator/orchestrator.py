# src/orchestrator/orchestrator.py
"""Orquestador central — coordina Bot, LLM, BD y Calendar."""

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from src.calendar_api import (
    build_completed_description,
    build_event_description,
    build_event_title,
    get_color_for_service,
)
from src.calendar_api.async_wrapper import AsyncGoogleCalendarClient
from src.config import Settings
from src.core.result import AvailableSlot, Result, ResultStatus
from src.db.models import Cliente, EstadoEvento, Evento, Prioridad, TipoServicio
from src.db.repository import Repository
from src.llm.parser import LLMParser
from src.llm.schemas import Intent

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class Orchestrator:
    """Cerebro del sistema: media entre todos los módulos.

    Recibe las solicitudes de los handlers de Telegram, coordina con el LLM
    para interpretar mensajes, ejecuta operaciones en la BD y el calendario,
    y devuelve resultados tipados (Result) al handler.
    """

    def __init__(
        self,
        repository: Repository,
        calendar_client: AsyncGoogleCalendarClient,
        llm_parser: LLMParser,
        settings: Settings,
    ):
        self.repo = repository
        self.calendar = calendar_client
        self.parser = llm_parser
        self.settings = settings

    # ── Creación de evento ────────────────────────────────────────────────

    async def create_event_from_text(self, text: str, user_id: int) -> Result:
        """Flujo completo de creación de evento desde texto natural.

        Parsea el mensaje, valida datos, resuelve cliente, verifica
        disponibilidad y prepara el evento para confirmación. NO persiste
        hasta que se llame a save_confirmed_event().

        Args:
            text: Mensaje del usuario describiendo el evento.
            user_id: ID de Telegram del usuario.

        Returns:
            Result con el evento listo para confirmar, o pidiendo más datos.
        """
        try:
            # 1. Parsear el mensaje
            parsed = await self.parser.parse_create_event(text)

            # 2. Si falta la fecha, preguntar SOLO por la fecha (nunca asumir "hoy")
            if parsed.fecha is None:
                return Result.needs_clarification(
                    question="¿Para qué fecha es el evento?"
                )

            # 3. Si tiene fecha pero falta la hora: calcular slots disponibles
            if parsed.has_date_but_no_time:
                date_ok, date_msg = _validate_event_date(parsed.fecha)
                if not date_ok:
                    return Result.error(message=date_msg)

                slots = await self._get_available_slots(parsed.fecha)
                if not slots:
                    return Result.needs_clarification(
                        question=(
                            f"No hay horarios disponibles para el "
                            f"{parsed.fecha.strftime('%d/%m/%Y')}. "
                            f"¿Querés elegir otro día?"
                        ),
                    )
                return Result(
                    status=ResultStatus.NEEDS_INPUT,
                    question="Elegí un horario disponible:",
                    data={"available_slots": slots, "parsed": parsed},
                )

            # 4. Si faltan otros datos → preguntar
            if parsed.needs_clarification:
                return Result.needs_clarification(
                    question=parsed.clarification_question
                    or "Necesito más información para crear el evento.",
                )

            # 5. Validar fecha+hora (no pasada, dentro del horario laboral)
            dt_ok, dt_msg = _validate_event_datetime(parsed.fecha, parsed.hora)
            if not dt_ok:
                return Result.error(message=dt_msg)

            wh_ok, wh_msg = _validate_work_hours(
                parsed.hora,
                parsed.duracion_minutos or 60,
                parsed.fecha.weekday(),
                self.settings,
            )
            if not wh_ok:
                return Result.error(message=wh_msg)

            # 6. Buscar o crear cliente
            cliente = await self._resolve_cliente(parsed)

            # 7. Verificar disponibilidad (con bypass si es prioridad alta)
            duracion = parsed.duracion_minutos or 60
            if not parsed.is_high_priority:
                conflict = await self._check_availability(
                    parsed.fecha, parsed.hora, duracion
                )
                if conflict:
                    slots = await self._get_available_slots(parsed.fecha)
                    if not slots:
                        return Result(
                            status=ResultStatus.CONFLICT,
                            message=(
                                f"Ya hay un evento agendado a esa hora ({conflict}). "
                                f"No quedan horarios disponibles para ese día. "
                                f"¿Querés elegir otro día?"
                            ),
                        )
                    return Result(
                        status=ResultStatus.CONFLICT,
                        message=(
                            f"Ya hay un evento agendado a esa hora ({conflict}). "
                            f"Estos son los horarios disponibles:"
                        ),
                        data={"available_slots": slots},
                    )

            # 8. Preparar evento (sin guardar — esperar confirmación)
            fecha_hora = datetime.combine(parsed.fecha, parsed.hora, tzinfo=TIMEZONE)
            evento_model = Evento(
                cliente_id=cliente.id,
                tipo_servicio=parsed.tipo_servicio,
                prioridad=parsed.prioridad,
                fecha_hora=fecha_hora,
                duracion_minutos=duracion,
                notas=parsed.notas,
            )

            # 9. Devolver evento listo para confirmación
            return Result.success(
                data={
                    "evento": evento_model,
                    "cliente": cliente,
                    "parsed": parsed,
                },
                message="Evento listo para confirmar.",
            )

        except Exception as e:
            logger.error("Error en create_event_from_text: %s", e, exc_info=True)
            return Result.error(
                message="No pude procesar tu mensaje. Intentá de nuevo."
            )

    async def confirm_slot_selection(
        self,
        parsed,
        selected_time: str,
        duration_minutes: int,
        user_id: int,
    ) -> Result:
        """Confirma la selección de horarios y prepara el evento.

        Se usa cuando el usuario ya eligió un slot de la lista de horarios
        disponibles. Recibe el ParsedEvent ya parseado (con fecha) y la hora
        seleccionada, sin necesidad de volver a parsear con el LLM.

        Args:
            parsed: ParsedEvent con los datos ya extraídos (fecha incluida).
            selected_time: Hora seleccionada en formato "HH:MM".
            duration_minutes: Duración en minutos (número de slots * 60).
            user_id: ID de Telegram del usuario.

        Returns:
            Result con el evento listo para confirmar.
        """
        try:
            time_obj = time.fromisoformat(selected_time)

            duracion = duration_minutes

            date_ok, date_msg = _validate_event_date(parsed.fecha)
            if not date_ok:
                return Result.error(message=date_msg)

            dt_ok, dt_msg = _validate_event_datetime(parsed.fecha, time_obj)
            if not dt_ok:
                return Result.error(message=dt_msg)

            wh_ok, wh_msg = _validate_work_hours(
                time_obj,
                duracion,
                parsed.fecha.weekday(),
                self.settings,
            )
            if not wh_ok:
                return Result.error(message=wh_msg)

            cliente = await self._resolve_cliente(parsed)

            if not parsed.is_high_priority:
                conflict = await self._check_availability(
                    parsed.fecha, time_obj, duracion
                )
                if conflict:
                    slots = await self._get_available_slots(parsed.fecha)
                    if not slots:
                        return Result(
                            status=ResultStatus.CONFLICT,
                            message=(
                                f"Ya hay un evento agendado a esa hora ({conflict}). "
                                f"No quedan horarios disponibles para ese día. "
                                f"¿Querés elegir otro día?"
                            ),
                        )
                    return Result(
                        status=ResultStatus.CONFLICT,
                        message=(
                            f"Ya hay un evento agendado a esa hora ({conflict}). "
                            f"Estos son los horarios disponibles:"
                        ),
                        data={"available_slots": slots},
                    )

            fecha_hora = datetime.combine(parsed.fecha, time_obj, tzinfo=TIMEZONE)
            evento_model = Evento(
                cliente_id=cliente.id,
                tipo_servicio=parsed.tipo_servicio,
                prioridad=parsed.prioridad,
                fecha_hora=fecha_hora,
                duracion_minutos=duracion,
                notas=parsed.notas,
            )

            return Result.success(
                data={
                    "evento": evento_model,
                    "cliente": cliente,
                    "parsed": parsed,
                },
                message="Evento listo para confirmar.",
            )

        except Exception as e:
            logger.error("Error en confirm_slot_selection: %s", e, exc_info=True)
            return Result.error(
                message="No pude confirmar la selección. Intentá de nuevo."
            )

    async def save_confirmed_event(
        self, evento: Evento, cliente: Cliente, parsed=None
    ) -> Result:
        """Guarda un evento ya confirmado por el usuario.

        Se llama SOLO después de que el usuario presionó "Confirmar".
        Hace: BD insert + Google Calendar create (transaccional).

        Args:
            evento: Evento Pydantic a persistir.
            cliente: Cliente asociado al evento.
            parsed: ParsedEvent original (para datos extra como dirección).

        Returns:
            Result exitoso con el evento guardado, o error si falla.
        """
        try:
            # 1. Crear en BD
            evento_id = await self.repo.create_evento(evento)
            evento.id = evento_id

            # 2. Crear en Google Calendar
            try:
                title = build_event_title(
                    cliente.nombre,
                    cliente.telefono or "",
                )
                direccion = (
                    cliente.direccion or (parsed.direccion if parsed else "") or ""
                )
                description = build_event_description(
                    tipo_servicio=evento.tipo_servicio.value,
                    direccion=direccion,
                    notas=evento.notas or "",
                )
                color_id = get_color_for_service(evento.tipo_servicio.value)

                google_event_id = await self.calendar.create_event(
                    title=title,
                    location=direccion,
                    description=description,
                    start_datetime=evento.fecha_hora,
                    duration_minutes=evento.duracion_minutos,
                    color_id=color_id,
                )
                await self.repo.update_evento(
                    evento.id, google_event_id=google_event_id
                )
                evento.google_event_id = google_event_id

            except Exception as e:
                # Rollback: eliminar de la BD si Calendar falla
                logger.error("Calendar falló, rollback BD: %s", e)
                await self.repo.delete_evento(evento.id)
                return Result.error(message=f"Error al crear en Calendar: {e}")

            # 3. Éxito
            logger.info(
                "Evento creado: id=%d, google_id=%s",
                evento.id,
                evento.google_event_id,
            )
            return Result.success(
                data=evento,
                message="Evento creado correctamente.",
            )

        except Exception as e:
            logger.error("Error en save_confirmed_event: %s", e, exc_info=True)
            return Result.error(message=f"Error al guardar el evento: {e}")

    # ── Edición de evento ─────────────────────────────────────────────────

    async def edit_event_from_text(
        self, text: str, evento: Evento, user_id: int
    ) -> Result:
        """Parsea cambios solicitados sobre un evento existente.

        Args:
            text: Texto del usuario describiendo los cambios.
            evento: Evento actual a modificar.
            user_id: ID de Telegram del usuario.

        Returns:
            Result con dict de cambios a aplicar, o pidiendo más datos.
        """
        try:
            parsed_edit = await self.parser.parse_edit_event(text, evento)

            if parsed_edit.clarification_question:
                return Result.needs_clarification(
                    question=parsed_edit.clarification_question,
                )

            if not parsed_edit.changes:
                return Result.needs_clarification(
                    question="No detecté cambios en tu mensaje. "
                    "¿Qué querés modificar del evento?",
                )

            return Result.success(data=parsed_edit.changes)

        except Exception as e:
            logger.error("Error en edit_event_from_text: %s", e, exc_info=True)
            return Result.error(
                message="No pude interpretar los cambios. Intentá de nuevo."
            )

    async def apply_event_changes(self, evento_id: int, changes: dict) -> Result:
        """Aplica cambios a un evento en BD y Calendar.

        Args:
            evento_id: ID del evento a modificar.
            changes: Diccionario con los campos y valores nuevos.

        Returns:
            Result exitoso o error.
        """
        try:
            evento = await self.repo.get_evento_by_id(evento_id)
            if not evento:
                return Result.error(message="Evento no encontrado.")

            # Preparar kwargs para el repository
            update_kwargs = {}
            for field, value in changes.items():
                if field == "tipo_servicio":
                    try:
                        update_kwargs["tipo_servicio"] = TipoServicio(value)
                    except ValueError:
                        update_kwargs["tipo_servicio"] = TipoServicio.OTRO
                elif field == "prioridad":
                    try:
                        update_kwargs["prioridad"] = Prioridad(value)
                    except ValueError:
                        pass
                elif field == "fecha_hora":
                    update_kwargs["fecha_hora"] = datetime.fromisoformat(value)
                elif field == "duracion_minutos":
                    update_kwargs["duracion_minutos"] = int(value)
                elif field == "notas":
                    update_kwargs["notas"] = value

            if not update_kwargs:
                return Result.error(message="No hay cambios válidos para aplicar.")

            # Guardar estado previo para posible rollback
            old_values = {
                k: getattr(evento, k) for k in update_kwargs if hasattr(evento, k)
            }

            # 1. Actualizar en BD
            await self.repo.update_evento(evento_id, **update_kwargs)

            # 2. Actualizar en Calendar (si tiene google_event_id)
            if evento.google_event_id:
                try:
                    cal_updates = {}
                    if "fecha_hora" in update_kwargs:
                        cal_updates["start_datetime"] = update_kwargs["fecha_hora"]
                    if "tipo_servicio" in update_kwargs:
                        cal_updates["color_id"] = get_color_for_service(
                            update_kwargs["tipo_servicio"].value
                        )
                    if "notas" in update_kwargs:
                        cal_updates["description"] = build_event_description(
                            tipo_servicio=(
                                update_kwargs.get("tipo_servicio", evento.tipo_servicio)
                            ).value,
                            direccion="",
                            notas=update_kwargs.get("notas", evento.notas or ""),
                        )
                    if cal_updates:
                        await self.calendar.update_event(
                            evento.google_event_id, **cal_updates
                        )
                except Exception as e:
                    # Rollback BD
                    logger.error("Calendar update falló, rollback BD: %s", e)
                    await self.repo.update_evento(evento_id, **old_values)
                    return Result.error(message=f"Error al actualizar en Calendar: {e}")

            logger.info("Evento %d actualizado: %s", evento_id, list(changes.keys()))
            return Result.success(message="Evento actualizado correctamente.")

        except Exception as e:
            logger.error("Error en apply_event_changes: %s", e, exc_info=True)
            return Result.error(message=f"Error al aplicar cambios: {e}")

    # ── Eliminación de evento ─────────────────────────────────────────────

    async def delete_event(self, evento_id: int) -> Result:
        """Elimina un evento de Calendar y BD.

        Sigue el orden: Calendar primero, BD después. Si Calendar falla,
        solo marca como cancelado en BD.

        Args:
            evento_id: ID del evento a eliminar.

        Returns:
            Result exitoso o error.
        """
        try:
            evento = await self.repo.get_evento_by_id(evento_id)
            if not evento:
                return Result.error(message="Evento no encontrado.")

            # 1. Eliminar de Calendar
            if evento.google_event_id:
                try:
                    await self.calendar.delete_event(evento.google_event_id)
                except Exception as e:
                    logger.warning(
                        "No se pudo eliminar de Calendar (id=%s): %s",
                        evento.google_event_id,
                        e,
                    )
                    # Si Calendar falla, solo cancelar en BD
                    await self.repo.update_evento(
                        evento_id, estado=EstadoEvento.CANCELADO
                    )
                    return Result.success(
                        message="Evento cancelado (no se pudo eliminar del calendario)."
                    )

            # 2. Eliminar de BD
            await self.repo.delete_evento(evento_id)

            logger.info("Evento %d eliminado", evento_id)
            return Result.success(message="Evento eliminado correctamente.")

        except Exception as e:
            logger.error("Error en delete_event: %s", e, exc_info=True)
            return Result.error(message=f"Error al eliminar el evento: {e}")

    # ── Cierre de servicio ────────────────────────────────────────────────

    async def parse_closure_text(self, text: str) -> Result:
        """Parsea datos de cierre de servicio desde texto natural.

        Args:
            text: Mensaje del usuario con trabajo realizado, monto, notas.

        Returns:
            Result con dict de datos de cierre, o pidiendo más datos.
        """
        try:
            parsed = await self.parser.parse_closure(text)

            if parsed.clarification_question:
                return Result.needs_clarification(
                    question=parsed.clarification_question,
                )

            closure_data = {}
            if parsed.trabajo_realizado:
                closure_data["trabajo_realizado"] = parsed.trabajo_realizado
            if parsed.monto_cobrado is not None:
                closure_data["monto_cobrado"] = parsed.monto_cobrado
            if parsed.notas_cierre:
                closure_data["notas_cierre"] = parsed.notas_cierre

            if not closure_data:
                return Result.needs_clarification(
                    question="¿Qué trabajo se realizó y cuánto se cobró?",
                )

            return Result.success(data=closure_data)

        except Exception as e:
            logger.error("Error en parse_closure_text: %s", e, exc_info=True)
            return Result.error(
                message="No pude interpretar los datos de cierre. Intentá de nuevo."
            )

    async def complete_event(self, evento_id: int, closure_data: dict) -> Result:
        """Completa un evento: actualiza BD (estado + cierre) y Calendar (verde).

        Args:
            evento_id: ID del evento a completar.
            closure_data: Dict con trabajo_realizado, monto_cobrado, notas_cierre, fotos.

        Returns:
            Result exitoso o error.
        """
        try:
            evento = await self.repo.get_evento_by_id(evento_id)
            if not evento:
                return Result.error(message="Evento no encontrado.")

            # Preparar datos de cierre para el repository
            repo_closure = {}
            if "trabajo_realizado" in closure_data:
                repo_closure["trabajo_realizado"] = closure_data["trabajo_realizado"]
            if "monto_cobrado" in closure_data:
                repo_closure["monto_cobrado"] = closure_data["monto_cobrado"]
            if "notas_cierre" in closure_data:
                repo_closure["notas_cierre"] = closure_data["notas_cierre"]
            if "fotos" in closure_data:
                repo_closure["fotos"] = closure_data["fotos"]

            # 1. Actualizar BD (estado=completado + datos cierre)
            await self.repo.complete_evento(evento_id, **repo_closure)

            # 2. Actualizar Calendar (color verde + descripción de cierre)
            if evento.google_event_id:
                try:
                    cliente = await self.repo.get_cliente_by_id(evento.cliente_id)
                    closure_description = build_completed_description(
                        tipo_servicio=evento.tipo_servicio.value,
                        direccion=cliente.direccion if cliente else "",
                        notas=evento.notas or "",
                        trabajo_realizado=closure_data.get("trabajo_realizado", ""),
                        monto_cobrado=closure_data.get("monto_cobrado", 0),
                        notas_cierre=closure_data.get("notas_cierre", ""),
                        fotos=closure_data.get("fotos"),
                    )
                    await self.calendar.complete_event(
                        evento.google_event_id,
                        closure_description,
                    )
                except Exception as e:
                    # BD ya actualizada — logueamos pero no revertimos
                    logger.error(
                        "Calendar complete falló (evento %d): %s",
                        evento_id,
                        e,
                    )

            logger.info("Evento %d completado", evento_id)
            return Result.success(message="Servicio completado correctamente.")

        except Exception as e:
            logger.error("Error en complete_event: %s", e, exc_info=True)
            return Result.error(message=f"Error al completar el evento: {e}")

    # ── Listados ──────────────────────────────────────────────────────────

    async def list_pending_events(self) -> list[Evento]:
        """Lista eventos pendientes agrupados.

        Returns:
            Lista de eventos con estado PENDIENTE ordenados por fecha.
        """
        return await self.repo.list_eventos_pendientes()

    async def list_today_events(self) -> list[Evento]:
        """Lista eventos pendientes de hoy.

        Returns:
            Lista de eventos del día actual.
        """
        return await self.repo.list_eventos_hoy()

    async def list_contacts(self) -> list[Cliente]:
        """Lista todos los clientes.

        Returns:
            Lista de clientes ordenados por nombre.
        """
        return await self.repo.list_clientes()

    # ── Mensajes naturales ────────────────────────────────────────────────

    async def handle_natural_message(self, text: str, user_id: int) -> Result:
        """Detecta la intención de un mensaje libre y delega al flujo correcto.

        Args:
            text: Mensaje del usuario.
            user_id: ID de Telegram.

        Returns:
            Result con la acción a tomar y datos asociados.
        """
        try:
            intent_result = await self.parser.detect_intent(text)
            intent = intent_result.intent

            match intent:
                case Intent.CREAR_EVENTO:
                    # No procesamos la creación aquí — retornamos la acción
                    # para que el handler de natural redirija al ConversationHandler
                    # de crear_evento (que maneja estados, clarificaciones, etc.)
                    return Result.success(
                        data={
                            "action": "crear_evento",
                            "original_text": text,
                        },
                        message="Entendí que querés crear un evento.",
                    )

                case Intent.VER_EVENTOS:
                    eventos = await self.list_pending_events()
                    return Result.success(
                        data={
                            "action": "ver_eventos",
                            "eventos": eventos,
                        },
                    )

                case Intent.ELIMINAR_EVENTO:
                    eventos = await self.list_pending_events()
                    return Result.success(
                        data={
                            "action": "eliminar",
                            "eventos": eventos,
                        },
                        message="Seleccioná el evento a eliminar:",
                    )

                case Intent.EDITAR_EVENTO:
                    eventos = await self.list_pending_events()
                    return Result.success(
                        data={
                            "action": "editar",
                            "eventos": eventos,
                        },
                        message="Seleccioná el evento a editar:",
                    )

                case Intent.TERMINAR_EVENTO:
                    eventos = await self.list_pending_events()
                    return Result.success(
                        data={
                            "action": "terminar",
                            "eventos": eventos,
                        },
                        message="Seleccioná el evento a completar:",
                    )

                case Intent.VER_CONTACTOS:
                    clientes = await self.list_contacts()
                    return Result.success(
                        data={
                            "action": "ver_contactos",
                            "clientes": clientes,
                        },
                    )

                case Intent.EDITAR_CONTACTO:
                    clientes = await self.list_contacts()
                    return Result.success(
                        data={
                            "action": "editar_contacto",
                            "clientes": clientes,
                        },
                        message="Seleccioná el contacto a editar:",
                    )

                case Intent.SALUDO:
                    return Result.success(
                        message="¡Hola! ¿En qué puedo ayudarte? "
                        "Usá /menu para ver las opciones.",
                    )

                case Intent.AYUDA:
                    return Result.success(
                        message="Puedo ayudarte a gestionar turnos de servicio técnico. "
                        "Usá /menu para ver todas las opciones disponibles.",
                    )

                case Intent.DESCONOCIDO:
                    return Result.needs_clarification(
                        "No entendí tu mensaje. Usá /menu para ver "
                        "las acciones disponibles.",
                    )

                case _:
                    return Result.needs_clarification(
                        "¿Podrías ser más específico? Decime qué querés hacer.",
                    )

        except Exception as e:
            logger.error("Error en handle_natural_message: %s", e, exc_info=True)
            return Result.error(
                message="No pude procesar tu mensaje. Intentá de nuevo."
            )

    # ── Disponibilidad (privado) ──────────────────────────────────────────

    async def _check_availability(
        self, fecha: date, hora: time, duracion: int = 60
    ) -> Optional[str]:
        """Verifica si un horario está disponible.

        Usa comparación estricta de rangos: un evento que TERMINA a las 16:00
        NO bloquea un evento que EMPIEZA a las 16:00 (consecutivos permitidos).

        Solo considera eventos PENDIENTES.

        Args:
            fecha: Fecha del evento.
            hora: Hora de inicio.
            duracion: Duración en minutos.

        Returns:
            None si disponible, string con info del conflicto si ocupado.
        """
        eventos_del_dia = await self.repo.list_eventos_by_date(fecha)

        new_start = datetime.combine(fecha, hora, tzinfo=TIMEZONE)
        new_end = new_start + timedelta(minutes=duracion)

        for ev in eventos_del_dia:
            # Ignorar eventos cancelados o completados
            if ev.estado != EstadoEvento.PENDIENTE:
                continue

            ev_start = ev.fecha_hora
            # Asegurar timezone-aware para comparación
            if ev_start.tzinfo is None:
                ev_start = ev_start.replace(tzinfo=TIMEZONE)
            ev_end = ev_start + timedelta(minutes=ev.duracion_minutos)

            # Consecutivos permitidos: usamos < y >, NO <= ni >=
            if new_start < ev_end and new_end > ev_start:
                return f"{ev.hora_formateada} - {ev_end.strftime('%H:%M')}"

        return None

    async def _get_available_slots(
        self, fecha: date, slot_duration: int = 60
    ) -> list[AvailableSlot]:
        """Calcula los bloques horarios disponibles para un día.

        Usa el horario laboral de Settings y resta los eventos existentes.
        Solo eventos PENDIENTES bloquean slots.

        Args:
            fecha: Fecha a consultar.
            slot_duration: Duración de cada slot en minutos.

        Returns:
            Lista de AvailableSlot con los bloques libres del día.
        """
        # Determinar horario laboral del día
        weekday = fecha.weekday()
        if weekday == 6:  # Domingo
            return []
        elif weekday == 5:  # Sábado
            work_start = time.fromisoformat(self.settings.work_days_saturday_start)
            work_end = time.fromisoformat(self.settings.work_days_saturday_end)
        else:  # Lunes a Viernes
            work_start = time.fromisoformat(self.settings.work_days_weekday_start)
            work_end = time.fromisoformat(self.settings.work_days_weekday_end)

        # Obtener eventos activos del día (solo pendientes bloquean slots)
        todos_eventos = await self.repo.list_eventos_by_date(fecha)
        eventos = [ev for ev in todos_eventos if ev.estado == EstadoEvento.PENDIENTE]

        # Generar slots dentro del horario laboral
        slots = []
        current = datetime.combine(fecha, work_start, tzinfo=TIMEZONE)
        end_of_day = datetime.combine(fecha, work_end, tzinfo=TIMEZONE)

        while current + timedelta(minutes=slot_duration) <= end_of_day:
            slot_start = current
            slot_end = current + timedelta(minutes=slot_duration)

            # Verificar si este slot se superpone con algún evento
            is_free = True
            for ev in eventos:
                ev_start = ev.fecha_hora
                if ev_start.tzinfo is None:
                    ev_start = ev_start.replace(tzinfo=TIMEZONE)
                ev_end = ev_start + timedelta(minutes=ev.duracion_minutos)

                # Consecutivos permitidos (< y >, no <= ni >=)
                if slot_start < ev_end and slot_end > ev_start:
                    is_free = False
                    break

            if is_free:
                slots.append(
                    AvailableSlot(
                        start=slot_start.time(),
                        end=slot_end.time(),
                    )
                )

            current += timedelta(minutes=slot_duration)

        return slots

    # ── Resolución de cliente (privado) ───────────────────────────────────

    async def _resolve_cliente(self, parsed) -> Cliente:
        """Busca un cliente existente o crea uno nuevo.

        Estrategia:
        1. Si hay teléfono → buscar por teléfono (match exacto)
        2. Si hay nombre → buscar fuzzy (threshold=80)
        3. Si no hay match → crear cliente nuevo

        Args:
            parsed: ParsedEvent con los datos del cliente.

        Returns:
            Cliente existente o recién creado.
        """
        # 1. Buscar por teléfono (exacto)
        if parsed.cliente_telefono:
            cliente = await self.repo.get_cliente_by_telefono(parsed.cliente_telefono)
            if cliente:
                return cliente

        # 2. Buscar por nombre (fuzzy, threshold=80)
        if parsed.cliente_nombre:
            matches = await self.repo.search_clientes_fuzzy(
                parsed.cliente_nombre, threshold=80, limit=3
            )
            if len(matches) == 1:
                return matches[0][0]  # (Cliente, score) → Cliente
            if matches:
                return matches[0][0]  # Mejor match

        # 3. Crear cliente nuevo
        new_cliente = Cliente(
            nombre=parsed.cliente_nombre or "Cliente sin nombre",
            telefono=parsed.cliente_telefono,
            direccion=getattr(parsed, "direccion", None),
        )
        client_id = await self.repo.create_cliente(new_cliente)
        new_cliente.id = client_id
        return new_cliente


# ── Funciones de validación (privadas del módulo) ─────────────────────────


def _validate_event_date(fecha: date) -> tuple[bool, str]:
    """Valida que la fecha no sea pasada ni mayor a 90 días.

    Args:
        fecha: Fecha a validar.

    Returns:
        Tupla (ok, mensaje_error).
    """
    today = datetime.now(TIMEZONE).date()
    if fecha < today:
        return False, "La fecha indicada ya pasó. Elegí otra."
    if fecha > today + timedelta(days=90):
        return False, "La fecha es demasiado lejana (máximo 90 días)."
    return True, ""


def _validate_event_datetime(fecha: date, hora: time) -> tuple[bool, str]:
    """Valida que la fecha+hora no sea pasada.

    Args:
        fecha: Fecha del evento.
        hora: Hora del evento.

    Returns:
        Tupla (ok, mensaje_error).
    """
    now = datetime.now(TIMEZONE)
    event_dt = datetime.combine(fecha, hora, tzinfo=TIMEZONE)
    if event_dt < now:
        return False, "La fecha y hora indicadas ya pasaron. Elegí otra."
    return True, ""


def _validate_work_hours(
    hora: time,
    duracion: int,
    weekday: int,
    settings: Settings,
) -> tuple[bool, str]:
    """Valida que el horario esté dentro de la jornada laboral.

    Args:
        hora: Hora de inicio del evento.
        duracion: Duración en minutos.
        weekday: Día de la semana (0=lunes, 6=domingo).
        settings: Configuración con horarios laborales.

    Returns:
        Tupla (ok, mensaje_error).
    """
    if weekday == 6:  # Domingo
        return False, "No se trabaja los domingos."

    if weekday == 5:  # Sábado
        work_start = time.fromisoformat(settings.work_days_saturday_start)
        work_end = time.fromisoformat(settings.work_days_saturday_end)
    else:  # Lunes a Viernes
        work_start = time.fromisoformat(settings.work_days_weekday_start)
        work_end = time.fromisoformat(settings.work_days_weekday_end)

    # Calcular hora de fin del evento
    start_dt = datetime.combine(date.today(), hora)
    end_dt = start_dt + timedelta(minutes=duracion)
    event_end_time = end_dt.time()

    if hora < work_start:
        return (
            False,
            f"El horario laboral empieza a las {work_start.strftime('%H:%M')}.",
        )
    if event_end_time > work_end:
        return (
            False,
            f"El evento terminaría después del horario laboral "
            f"({work_end.strftime('%H:%M')}).",
        )

    return True, ""
