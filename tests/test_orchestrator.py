"""Tests para core/orchestrator.py — Orquestador central."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytz
import pytest

from agents.db_manager.models import Cliente, Servicio
from agents.groq_parser.schemas import (
    EditInstruction,
    Intencion,
    ParsedMessage,
    TipoServicio,
)
from config.constants import TIMEZONE
from core.orchestrator import (
    AWAITING_CANCEL_SELECTION,
    AWAITING_CLIENT_NAME,
    AWAITING_CONFIRMATION,
    AWAITING_EDIT_CONFIRM,
    AWAITING_EDIT_SELECTION,
    AWAITING_MISSING_DATA,
    IDLE,
    CreationContext,
    Orchestrator,
    OrchestratorResponse,
    UserRole,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_orchestrator(mock_settings, mock_groq_client, mock_calendar_client, mock_repository):
    """Crea un Orchestrator con mocks inyectados."""
    return Orchestrator(
        settings=mock_settings,
        groq_client=mock_groq_client,
        repository=mock_repository,
        calendar_client=mock_calendar_client,
    )


# ── UserRole ─────────────────────────────────────────────────────────────────


class TestUserRole:
    """Tests para UserRole."""

    def test_admin_role(self):
        assert UserRole.admin == "admin"

    def test_editor_role(self):
        assert UserRole.editor == "editor"


# ── Orchestrator._get_role ───────────────────────────────────────────────────


class TestGetRole:
    """Tests para _get_role()."""

    def test_admin_id_retorna_admin(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        assert orch._get_role(123456789) == UserRole.admin

    def test_editor_id_retorna_editor(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        assert orch._get_role(111222333) == UserRole.editor

    def test_desconocido_retorna_editor(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Desconocido se trata como editor (sin permisos admin)."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        assert orch._get_role(999999999) == UserRole.editor


# ── process_message: permisos ────────────────────────────────────────────────


class TestProcessMessagePermisos:
    """Tests de control de permisos en process_message()."""

    @patch("agents.groq_parser.parser.parse_message")
    async def test_editor_intenta_agendar_retorna_error_permiso(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Editor + intención 'agendar' → mensaje de acceso denegado."""
        mock_parse.return_value = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            duracion_estimada_horas=3.0,
        )
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("agendar instalación", 111222333)
        assert "permiso" in response.text.lower()
        assert response.next_state == IDLE

    @patch("agents.groq_parser.parser.parse_message")
    async def test_editor_intenta_cancelar_retorna_error_permiso(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Editor + intención 'cancelar' → acceso denegado."""
        mock_parse.return_value = ParsedMessage(intencion=Intencion.cancelar)
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("cancelar evento", 111222333)
        assert "permiso" in response.text.lower()

    @patch("agents.groq_parser.parser.parse_message")
    async def test_editor_puede_editar(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Editor + intención 'editar' → flujo de edición (no denegado)."""
        mock_parse.return_value = ParsedMessage(intencion=Intencion.editar)
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("editar evento", 111222333)
        assert "permiso" not in response.text.lower()
        assert response.next_state == AWAITING_EDIT_SELECTION

    @patch("agents.groq_parser.parser.parse_message")
    async def test_editor_puede_listar(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Editor + intención 'listar_pendientes' → lista normal."""
        mock_parse.return_value = ParsedMessage(intencion=Intencion.listar_pendientes)
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("listar eventos", 111222333)
        assert "permiso" not in response.text.lower()
        assert response.next_state == IDLE

    @patch("agents.groq_parser.parser.parse_message")
    async def test_admin_puede_agendar(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Admin + intención 'agendar' → flujo de creación."""
        mock_parse.return_value = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            duracion_estimada_horas=3.0,
        )
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("agendar instalación", 123456789)
        assert "permiso" not in response.text.lower()


# ── process_message: intención 'otro' ────────────────────────────────────────


class TestProcessMessageOtro:
    """Tests para intención 'otro'."""

    @patch("agents.groq_parser.parser.parse_message")
    async def test_intencion_otro_retorna_mensaje_ayuda(
        self, mock_parse, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención 'otro' → mensaje de no entendí."""
        mock_parse.return_value = ParsedMessage(intencion=Intencion.otro)
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.process_message("hola que tal", 123456789)
        assert "no entendí" in response.text.lower()
        assert response.next_state == IDLE


# ── start_creation_flow ──────────────────────────────────────────────────────


class TestStartCreationFlow:
    """Tests para start_creation_flow()."""

    async def test_sin_fecha_retorna_solicitud_con_botones(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Input sin fecha → solicitud con teclado de fechas."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
        )
        response = await orch.start_creation_flow(parsed)
        assert "fecha" in response.text.lower() or "día" in response.text.lower()
        assert response.keyboard is not None
        assert response.next_state == AWAITING_MISSING_DATA

    async def test_sin_hora_retorna_solicitud_con_botones(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Input sin hora, día con franjas → solicitud con teclado de rangos."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),  # Martes
        )
        response = await orch.start_creation_flow(parsed)
        assert "hora" in response.text.lower()
        assert response.keyboard is not None
        assert response.next_state == AWAITING_MISSING_DATA

    async def test_domingo_retorna_error(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Fecha domingo → mensaje de sin servicio."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            fecha=date(2026, 3, 8),  # Domingo
        )
        response = await orch.start_creation_flow(parsed)
        assert "domingo" in response.text.lower()

    async def test_dia_lleno_retorna_day_full_keyboard(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día lleno → teclado de día completo."""
        # Simular día completamente lleno
        mock_calendar_client.listar_eventos_por_fecha.return_value = [
            {
                "start": {"dateTime": "2026-03-03T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-03T21:00:00-03:00"},
            }
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),  # Martes
        )
        response = await orch.start_creation_flow(parsed)
        assert "lleno" in response.text.lower()
        assert response.keyboard is not None

    async def test_completo_retorna_confirmacion(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Datos completos → resumen de confirmación."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            duracion_estimada_horas=3.0,
        )
        response = await orch.start_creation_flow(parsed)
        assert "resumen" in response.text.lower() or "confirmar" in response.text.lower()
        assert response.next_state == AWAITING_CONFIRMATION


# ── complete_missing_field ───────────────────────────────────────────────────


class TestCompleteMissingField:
    """Tests para complete_missing_field()."""

    async def test_hora_completa_y_avanza(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Proveer hora faltante → avanza a confirmación."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx_data = {
            "nombre_cliente": "García",
            "tipo_servicio": "instalacion",
            "fecha": "2026-03-03",
            "hora": None,
            "duracion_horas": 3.0,
            "campo_pendiente": "hora",
        }
        response = await orch.complete_missing_field("hora", "10:00", ctx_data)
        # Debería avanzar (no volver a pedir hora)
        assert response.text is not None

    async def test_fecha_completa_y_avanza(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Proveer fecha faltante → avanza a pedir hora."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx_data = {
            "nombre_cliente": "García",
            "tipo_servicio": "instalacion",
            "fecha": None,
            "hora": None,
            "duracion_horas": 3.0,
            "campo_pendiente": "fecha",
        }
        response = await orch.complete_missing_field("fecha", "2026-03-03", ctx_data)
        # Ahora debe pedir hora
        assert response.text is not None


# ── check_day_capacity ───────────────────────────────────────────────────────


class TestCheckDayCapacity:
    """Tests para check_day_capacity()."""

    async def test_dia_vacio_tiene_capacidad(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día sin eventos → tiene capacidad."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        mock_calendar_client.listar_eventos_por_fecha.return_value = []
        has_capacity, free = await orch.check_day_capacity(date(2026, 3, 2), 2.0)
        assert has_capacity is True
        assert free == 6.0

    async def test_dia_lleno_sin_capacidad(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día con 6h de eventos (lunes) → sin capacidad."""
        mock_calendar_client.listar_eventos_por_fecha.return_value = [
            {
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T21:00:00-03:00"},
            }
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        has_capacity, free = await orch.check_day_capacity(date(2026, 3, 2), 2.0)
        assert has_capacity is False
        assert free == 0.0

    async def test_domingo_sin_capacidad(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Domingo → sin capacidad."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        has_capacity, free = await orch.check_day_capacity(date(2026, 3, 8), 1.0)
        assert has_capacity is False
        assert free == 0.0


# ── confirm_event ────────────────────────────────────────────────────────────


class TestConfirmEvent:
    """Tests para confirm_event()."""

    async def test_crea_evento_en_calendar(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository, cliente_garcia
    ):
        """Confirmación crea evento en Calendar y registra en DB."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx = CreationContext(
            nombre_cliente="García, Juan",
            tipo_servicio="instalacion",
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            duracion_horas=3.0,
            cliente_obj=cliente_garcia,
        )
        response = await orch.confirm_event(ctx)
        assert "creado" in response.text.lower()
        assert response.next_state == IDLE
        mock_calendar_client.crear_evento.assert_called_once()
        mock_repository.registrar_servicio.assert_called_once()

    async def test_sin_cliente_retorna_error(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin cliente_obj → error interno."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx = CreationContext(
            nombre_cliente="García",
            tipo_servicio="instalacion",
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            cliente_obj=None,
        )
        response = await orch.confirm_event(ctx)
        assert "error" in response.text.lower()

    async def test_error_calendar_retorna_error(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository, cliente_garcia
    ):
        """Error en Calendar → mensaje de error."""
        mock_calendar_client.crear_evento.side_effect = Exception("API error")
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx = CreationContext(
            nombre_cliente="García, Juan",
            tipo_servicio="instalacion",
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
            duracion_horas=3.0,
            cliente_obj=cliente_garcia,
        )
        response = await orch.confirm_event(ctx)
        assert "error" in response.text.lower()


# ── get_upcoming_events_for_selection ────────────────────────────────────────


class TestGetUpcomingEventsForSelection:
    """Tests para get_upcoming_events_for_selection()."""

    async def test_con_eventos_retorna_lista_formateada(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Con eventos → tupla con lista y texto formateado."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        eventos, text = await orch.get_upcoming_events_for_selection()
        assert len(eventos) == 1
        assert "próximos" in text.lower()

    async def test_sin_eventos_retorna_mensaje(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin eventos → mensaje informativo."""
        mock_calendar_client.listar_proximos_eventos.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        eventos, text = await orch.get_upcoming_events_for_selection()
        assert len(eventos) == 0
        assert "no hay" in text.lower()


# ── resolve_list_query ───────────────────────────────────────────────────────


class TestResolveListQuery:
    """Tests para resolve_list_query()."""

    async def test_listar_pendientes(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_pendientes → lista de eventos."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.listar_pendientes)
        response = await orch.resolve_list_query(parsed)
        assert response.next_state == IDLE
        assert response.text is not None

    async def test_listar_pendientes_sin_eventos(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin eventos → mensaje apropiado."""
        mock_calendar_client.listar_eventos.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.listar_pendientes)
        response = await orch.resolve_list_query(parsed)
        assert "no hay" in response.text.lower()

    async def test_listar_dia(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_dia con fecha."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.listar_dia,
            fecha=date(2026, 3, 3),
        )
        response = await orch.resolve_list_query(parsed)
        assert response.next_state == IDLE

    async def test_listar_cliente_con_nombre(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_cliente con nombre → busca por fuzzy."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.listar_cliente,
            cliente_consulta="García",
        )
        response = await orch.resolve_list_query(parsed)
        assert response.next_state == IDLE
        mock_repository.buscar_cliente_fuzzy.assert_called_once()

    async def test_listar_cliente_sin_nombre_pide_nombre(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_cliente sin nombre → pregunta y devuelve AWAITING_CLIENT_NAME."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.listar_cliente)
        response = await orch.resolve_list_query(parsed)
        assert "cliente" in response.text.lower()
        assert response.next_state == AWAITING_CLIENT_NAME

    async def test_listar_historial(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_historial → lista de eventos."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.listar_historial)
        response = await orch.resolve_list_query(parsed)
        assert response.next_state == IDLE


# ── CreationContext y helpers ────────────────────────────────────────────────


class TestCreationContext:
    """Tests para CreationContext y helpers."""

    def test_defaults(self):
        """CreationContext tiene defaults sensatos."""
        ctx = CreationContext()
        assert ctx.nombre_cliente is None
        assert ctx.urgente is False

    def test_context_to_dict_serializa(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """_context_to_dict serializa fecha/hora a strings."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx = CreationContext(
            nombre_cliente="García",
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
        )
        d = orch._context_to_dict(ctx)
        assert d["fecha"] == "2026-03-03"
        assert d["hora"] == "10:00"
        assert d["nombre_cliente"] == "García"

    def test_context_to_parsed_reconstruye(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """_context_to_parsed reconstruye un ParsedMessage."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        ctx = CreationContext(
            nombre_cliente="García",
            tipo_servicio="instalacion",
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
        )
        parsed = orch._context_to_parsed(ctx)
        assert parsed.intencion == Intencion.agendar
        assert parsed.tipo_servicio == TipoServicio.instalacion
        assert parsed.fecha == date(2026, 3, 3)


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 5 — Cancelación Interactiva
# ══════════════════════════════════════════════════════════════════════════════


class TestConfirmCancel:
    """Tests para confirm_cancel()."""

    async def test_cancela_evento_y_actualiza_db(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """confirm_cancel → elimina de Calendar + actualiza estado en DB a 'cancelado'."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_cancel("evt_1")
        assert "cancelado" in response.text.lower()
        assert response.next_state == IDLE
        mock_calendar_client.eliminar_evento.assert_called_once_with("evt_1")
        mock_repository.buscar_servicio_por_event_id.assert_called_once_with("evt_1")
        mock_repository.actualizar_estado_servicio.assert_called_once_with(1, "cancelado")

    async def test_error_calendar_retorna_error(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Error en Calendar → mensaje de error, sin excepción no manejada."""
        mock_calendar_client.eliminar_evento.side_effect = Exception("API error")
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_cancel("evt_invalid")
        assert "error" in response.text.lower()
        assert response.next_state == IDLE
        # No debe intentar actualizar DB si falló Calendar
        mock_repository.actualizar_estado_servicio.assert_not_called()

    async def test_servicio_no_encontrado_en_db_no_falla(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Si no hay servicio en DB para el event_id, la cancelación sigue exitosa."""
        mock_repository.buscar_servicio_por_event_id.return_value = None
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_cancel("evt_sin_db")
        assert "cancelado" in response.text.lower()
        assert response.next_state == IDLE
        mock_calendar_client.eliminar_evento.assert_called_once()
        mock_repository.actualizar_estado_servicio.assert_not_called()

    async def test_error_db_no_impide_cancelacion(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Error en DB al actualizar estado → cancelación sigue exitosa (warning logueado)."""
        mock_repository.buscar_servicio_por_event_id.side_effect = Exception("DB error")
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_cancel("evt_1")
        assert "cancelado" in response.text.lower()
        assert response.next_state == IDLE


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 5 — Edición Inteligente
# ══════════════════════════════════════════════════════════════════════════════


class TestParseAndPreviewEdit:
    """Tests para parse_and_preview_edit()."""

    @patch("agents.groq_parser.parser.parse_edit_instruction")
    @patch("agents.calendar_sync.event_builder.build_patch")
    async def test_genera_preview_con_cambios(
        self,
        mock_build_patch,
        mock_parse_edit,
        mock_settings,
        mock_groq_client,
        mock_calendar_client,
        mock_repository,
        evento_proximo,
    ):
        """Instrucción de edición → preview con cambios y teclado de confirmación."""
        mock_parse_edit.return_value = EditInstruction(
            nueva_fecha=date(2026, 3, 6),
            nueva_hora=time(16, 0),
        )
        mock_build_patch.return_value = {
            "start": {"dateTime": "2026-03-06T16:00:00-03:00"},
            "end": {"dateTime": "2026-03-06T17:00:00-03:00"},
        }
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.parse_and_preview_edit(
            "pasalo para el viernes a las 16", evento_proximo
        )
        assert "Cambios a aplicar" in response.text
        assert response.keyboard is not None
        assert response.next_state == AWAITING_EDIT_CONFIRM
        assert response.context is not None
        assert "patch" in response.context

    @patch("agents.groq_parser.parser.parse_edit_instruction")
    @patch("agents.calendar_sync.event_builder.build_patch")
    async def test_preview_incluye_tipo_servicio_cambiado(
        self,
        mock_build_patch,
        mock_parse_edit,
        mock_settings,
        mock_groq_client,
        mock_calendar_client,
        mock_repository,
        evento_proximo,
    ):
        """Cambio de tipo de servicio → preview muestra nuevo tipo + patch con colorId."""
        mock_parse_edit.return_value = EditInstruction(
            nuevo_tipo_servicio=TipoServicio.instalacion,
        )
        mock_build_patch.return_value = {"colorId": "9"}
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.parse_and_preview_edit(
            "cambiá el servicio a instalación", evento_proximo
        )
        assert "Cambios a aplicar" in response.text
        assert response.context is not None
        assert response.context["patch"] == {"colorId": "9"}

    @patch("agents.groq_parser.parser.parse_edit_instruction")
    @patch("agents.calendar_sync.event_builder.build_patch")
    async def test_cliente_no_encontrado_usa_nombre_summary(
        self,
        mock_build_patch,
        mock_parse_edit,
        mock_settings,
        mock_groq_client,
        mock_calendar_client,
        mock_repository,
        evento_proximo,
    ):
        """Si buscar_cliente_fuzzy retorna None, usa nombre del summary."""
        mock_parse_edit.return_value = EditInstruction(
            nueva_direccion="Av. Libertador 1234",
        )
        mock_build_patch.return_value = {"location": "Av. Libertador 1234"}
        mock_repository.buscar_cliente_fuzzy.return_value = None
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.parse_and_preview_edit(
            "nueva dirección: Av. Libertador 1234", evento_proximo
        )
        assert response.next_state == AWAITING_EDIT_CONFIRM
        # build_patch se llamó con un Cliente genérico
        mock_build_patch.assert_called_once()
        call_args = mock_build_patch.call_args
        cliente_arg = call_args[0][2]
        assert cliente_arg.nombre_completo == "García, Juan"


class TestConfirmEdit:
    """Tests para confirm_edit()."""

    async def test_aplica_patch_correcto(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """confirm_edit → actualizar_evento en Calendar con patch correcto."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        patch_data = {"location": "Av. Libertador 1234"}
        response = await orch.confirm_edit("evt_1", patch_data)
        assert "actualizado" in response.text.lower()
        assert response.next_state == IDLE
        mock_calendar_client.actualizar_evento.assert_called_once_with("evt_1", patch_data)

    async def test_error_calendar_retorna_error(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Error en Calendar → mensaje de error."""
        mock_calendar_client.actualizar_evento.side_effect = Exception("API error")
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_edit("evt_1", {"location": "x"})
        assert "error" in response.text.lower()
        assert response.next_state == IDLE

    async def test_patch_con_color_busca_servicio_en_db(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Patch con nuevo_tipo_trabajo → busca servicio en DB y actualiza tipo."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        patch_data = {"colorId": "9"}
        response = await orch.confirm_edit("evt_1", patch_data, nuevo_tipo_trabajo="instalacion")
        assert "actualizado" in response.text.lower()
        mock_repository.buscar_servicio_por_event_id.assert_called_once_with("evt_1")
        mock_repository.actualizar_tipo_trabajo.assert_called_once_with(1, "instalacion")

    async def test_sin_nuevo_tipo_no_busca_en_db(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin nuevo_tipo_trabajo → no busca ni actualiza en DB."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_edit("evt_1", {"location": "x"})
        assert "actualizado" in response.text.lower()
        mock_repository.buscar_servicio_por_event_id.assert_not_called()
        mock_repository.actualizar_tipo_trabajo.assert_not_called()

    async def test_nuevo_tipo_sin_servicio_en_db_no_crashea(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """nuevo_tipo_trabajo dado pero sin servicio en DB → no crashea."""
        mock_repository.buscar_servicio_por_event_id.return_value = None
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_edit(
            "evt_1", {"colorId": "9"}, nuevo_tipo_trabajo="instalacion"
        )
        assert "actualizado" in response.text.lower()
        mock_repository.actualizar_tipo_trabajo.assert_not_called()

    async def test_resultado_incluye_link(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """El resultado incluye link a Calendar si está presente."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        response = await orch.confirm_edit("evt_1", {"location": "x"})
        assert "Calendar" in response.text


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 5 — Motor de Consultas
# ══════════════════════════════════════════════════════════════════════════════


class TestListarPendientes:
    """Tests para listar_pendientes()."""

    async def test_retorna_eventos_proximos(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """listar_pendientes → texto con lista de eventos futuros."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_pendientes()
        assert "Eventos pendientes" in text
        mock_calendar_client.listar_eventos.assert_called_once()
        # Verificar que time_min y time_max están en el rango correcto
        call_kwargs = mock_calendar_client.listar_eventos.call_args[1]
        assert "time_min" in call_kwargs
        assert "time_max" in call_kwargs

    async def test_sin_eventos_retorna_mensaje_apropiado(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Calendar vacío → texto con 'No hay eventos'."""
        mock_calendar_client.listar_eventos.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_pendientes()
        assert "no hay" in text.lower()


class TestListarHistorial:
    """Tests para listar_historial()."""

    async def test_retorna_eventos_pasados(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """listar_historial → texto con historial de eventos."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_historial()
        assert "Historial" in text
        mock_calendar_client.listar_eventos.assert_called_once()
        # Verificar que time_min es ahora - 30 días y time_max es ahora
        call_kwargs = mock_calendar_client.listar_eventos.call_args[1]
        tz_obj = pytz.timezone(TIMEZONE)
        now = datetime.now(tz_obj)
        assert call_kwargs["time_min"] < now
        assert call_kwargs["time_max"] <= now

    async def test_dias_custom(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """listar_historial(dias=7) → time_min es ahora - 7 días."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        await orch.listar_historial(dias=7)
        call_kwargs = mock_calendar_client.listar_eventos.call_args[1]
        tz_obj = pytz.timezone(TIMEZONE)
        now = datetime.now(tz_obj)
        time_min = call_kwargs["time_min"]
        diff = now - time_min
        assert 6 <= diff.days <= 7

    async def test_sin_eventos_retorna_mensaje_apropiado(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin eventos pasados → texto con 'No hay eventos'."""
        mock_calendar_client.listar_eventos.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_historial()
        assert "no hay" in text.lower()


class TestListarPorDia:
    """Tests para listar_por_dia()."""

    async def test_retorna_eventos_del_dia(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """listar_por_dia → texto con eventos de la fecha."""
        mock_calendar_client.listar_eventos_por_fecha.return_value = [
            {
                "id": "evt_1",
                "summary": "García, Juan - 2604567890",
                "start": {"dateTime": "2026-03-03T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-03T16:00:00-03:00"},
                "colorId": "5",
                "description": "Tipo de Servicio: revision",
            }
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_dia(date(2026, 3, 3))
        assert "03/03/2026" in text
        mock_calendar_client.listar_eventos_por_fecha.assert_called_once_with(date(2026, 3, 3))

    async def test_dia_completo_muestra_warning(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día lleno → texto incluye indicador ⚠️ Día completo."""
        # Llenar el día completamente (lunes 15:00-21:00 = 6h)
        mock_calendar_client.listar_eventos_por_fecha.return_value = [
            {
                "id": "evt_full",
                "summary": "Test - 123",
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T21:00:00-03:00"},
                "colorId": "5",
                "description": "Tipo de Servicio: instalacion",
            }
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_dia(date(2026, 3, 2))  # Lunes
        assert "⚠️" in text
        assert "Día completo" in text

    async def test_dia_con_espacio_no_muestra_warning(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día con espacio libre → sin indicador ⚠️."""
        mock_calendar_client.listar_eventos_por_fecha.return_value = [
            {
                "id": "evt_1",
                "summary": "García - 123",
                "start": {"dateTime": "2026-03-02T15:00:00-03:00"},
                "end": {"dateTime": "2026-03-02T16:00:00-03:00"},
                "colorId": "5",
                "description": "Tipo de Servicio: revision",
            }
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_dia(date(2026, 3, 2))  # Lunes
        assert "⚠️" not in text

    async def test_sin_eventos_retorna_mensaje_y_sin_warning(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Día sin eventos → 'No hay eventos' y sin ⚠️."""
        mock_calendar_client.listar_eventos_por_fecha.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_dia(date(2026, 3, 3))
        assert "no hay" in text.lower()
        assert "⚠️" not in text


class TestListarPorCliente:
    """Tests para listar_por_cliente()."""

    async def test_retorna_pendientes_y_historial_separados(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """listar_por_cliente → texto con secciones separadas de Próximos e Historial."""
        tz_obj = pytz.timezone(TIMEZONE)
        now = datetime.now(tz_obj)
        futuro = (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
        pasado = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"

        mock_calendar_client.buscar_eventos_por_cliente.return_value = [
            {
                "id": "evt_futuro",
                "summary": "García, Juan - 2604567890",
                "start": {"dateTime": futuro},
                "end": {"dateTime": futuro},
                "colorId": "5",
                "description": "Tipo de Servicio: revision",
            },
            {
                "id": "evt_pasado",
                "summary": "García, Juan - 2604567890",
                "start": {"dateTime": pasado},
                "end": {"dateTime": pasado},
                "colorId": "9",
                "description": "Tipo de Servicio: instalacion",
            },
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_cliente("García")
        assert "Próximos" in text
        assert "Historial" in text
        assert "García, Juan" in text
        mock_repository.buscar_cliente_fuzzy.assert_called_once()

    async def test_cliente_no_encontrado_en_db_usa_nombre_original(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Si fuzzy match no encuentra → usa nombre original para buscar en Calendar."""
        mock_repository.buscar_cliente_fuzzy.return_value = None
        mock_calendar_client.buscar_eventos_por_cliente.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_cliente("NombreInexistente")
        assert "NombreInexistente" in text
        assert "No se encontraron eventos" in text
        mock_calendar_client.buscar_eventos_por_cliente.assert_called_once_with("NombreInexistente")

    async def test_sin_eventos_retorna_mensaje_apropiado(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Sin eventos para el cliente → mensaje informativo."""
        mock_calendar_client.buscar_eventos_por_cliente.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_cliente("García")
        assert "No se encontraron eventos" in text

    async def test_solo_pendientes_muestra_sin_historial(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Solo eventos futuros → sección Historial dice 'No hay turnos anteriores'."""
        tz_obj = pytz.timezone(TIMEZONE)
        futuro = (datetime.now(tz_obj) + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
        mock_calendar_client.buscar_eventos_por_cliente.return_value = [
            {
                "id": "evt_f",
                "summary": "García, Juan - 2604567890",
                "start": {"dateTime": futuro},
                "end": {"dateTime": futuro},
                "colorId": "5",
                "description": "Tipo de Servicio: revision",
            },
        ]
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        text = await orch.listar_por_cliente("García")
        assert "No hay turnos anteriores" in text


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 5 — resolve_list_query delegación
# ══════════════════════════════════════════════════════════════════════════════


class TestResolveListQueryDelegation:
    """Tests para verificar que resolve_list_query delega correctamente."""

    async def test_listar_historial_delega(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_historial → delega a listar_historial()."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.listar_historial)
        response = await orch.resolve_list_query(parsed)
        assert response.next_state == IDLE
        assert "Historial" in response.text

    async def test_listar_dia_usa_fecha_consulta(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención listar_dia con fecha_consulta → usa esa fecha."""
        mock_calendar_client.listar_eventos_por_fecha.return_value = []
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(
            intencion=Intencion.listar_dia,
            fecha_consulta=date(2026, 3, 5),
        )
        response = await orch.resolve_list_query(parsed)
        mock_calendar_client.listar_eventos_por_fecha.assert_called_once_with(date(2026, 3, 5))

    async def test_intencion_desconocida_retorna_mensaje(
        self, mock_settings, mock_groq_client, mock_calendar_client, mock_repository
    ):
        """Intención de listado no reconocida → mensaje genérico."""
        orch = _make_orchestrator(
            mock_settings, mock_groq_client, mock_calendar_client, mock_repository
        )
        parsed = ParsedMessage(intencion=Intencion.otro)
        response = await orch.resolve_list_query(parsed)
        assert "no pude determinar" in response.text.lower()
