"""Tests para agents/telegram_listener/commands.py y handler.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.telegram_listener.commands import (
    _format_uptime,
    clientes_command,
    help_command,
    reset_start_time,
    start_command,
    status_command,
)
from agents.telegram_listener.handler import (
    CREATION_HELP_TEXT,
    TIMEOUT_TEXT,
    _awaiting_client_name_handler,
    _button_cancelar_evento,
    _button_crear_turno,
    _button_editar_evento,
    _button_listar_eventos,
    _cancel_confirm_callback,
    _cancel_selection_callback,
    _confirmation_callback,
    _edit_confirm_callback,
    _edit_instruction_handler,
    _edit_selection_callback,
    _idle_text_handler,
    _send_orchestrator_response,
    _timeout_handler,
    build_conversation_handler,
)
from core.orchestrator import (
    AWAITING_CANCEL_CONFIRM,
    AWAITING_CANCEL_SELECTION,
    AWAITING_CLIENT_NAME,
    AWAITING_CONFIRMATION,
    AWAITING_CREATION_INPUT,
    AWAITING_EDIT_CONFIRM,
    AWAITING_EDIT_INSTRUCTION,
    AWAITING_EDIT_SELECTION,
    IDLE,
    OrchestratorResponse,
)


# ── _format_uptime ───────────────────────────────────────────────────────────


class TestFormatUptime:
    """Tests para _format_uptime()."""

    def test_solo_segundos(self):
        assert _format_uptime(45) == "45s"

    def test_minutos_y_segundos(self):
        assert _format_uptime(125) == "2m 5s"

    def test_horas_minutos_segundos(self):
        assert _format_uptime(3661) == "1h 1m 1s"

    def test_cero(self):
        assert _format_uptime(0) == "0s"


# ── start_command ────────────────────────────────────────────────────────────


class TestStartCommand:
    """Tests para /start."""

    async def test_admin_recibe_bienvenida_con_menu_admin(self, mock_telegram_update, mock_context):
        """Admin → bienvenida con menú de admin."""
        update = mock_telegram_update(user_id=123456789, first_name="Admin")
        await start_command(update, mock_context)
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Hola Admin" in call_args[0][0]

    async def test_editor_recibe_bienvenida_con_menu_editor(
        self, mock_telegram_update, mock_context
    ):
        """Editor → bienvenida con menú de editor."""
        update = mock_telegram_update(user_id=111222333, first_name="Editor")
        await start_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        assert "Hola Editor" in call_args[0][0]
        # No menciona crear/cancelar
        assert "Crear" not in call_args[0][0]


# ── help_command ─────────────────────────────────────────────────────────────


class TestHelpCommand:
    """Tests para /help."""

    async def test_admin_ve_ayuda_completa(self, mock_telegram_update, mock_context):
        """Admin ve todas las opciones incluyendo crear y cancelar."""
        update = mock_telegram_update(user_id=123456789)
        await help_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Admin" in text
        assert "Crear Turno" in text
        assert "Cancelar Evento" in text

    async def test_editor_ve_ayuda_limitada(self, mock_telegram_update, mock_context):
        """Editor ve solo editar y listar."""
        update = mock_telegram_update(user_id=111222333)
        await help_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Editor" in text
        assert "Crear Turno" not in text


# ── status_command ───────────────────────────────────────────────────────────


class TestStatusCommand:
    """Tests para /status."""

    async def test_editor_recibe_acceso_denegado(self, mock_telegram_update, mock_context):
        """Editor → mensaje de acceso denegado."""
        update = mock_telegram_update(user_id=111222333)
        await status_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        assert "administradores" in call_args[0][0].lower()

    async def test_admin_ve_estado(self, mock_telegram_update, mock_context):
        """Admin → respuesta con estado del sistema."""
        update = mock_telegram_update(user_id=123456789)
        reset_start_time()
        await status_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Estado del Sistema" in text


# ── clientes_command ─────────────────────────────────────────────────────────


class TestClientesCommand:
    """Tests para /clientes."""

    async def test_editor_recibe_acceso_denegado(self, mock_telegram_update, mock_context):
        """Editor → acceso denegado."""
        update = mock_telegram_update(user_id=111222333)
        await clientes_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        assert "administradores" in call_args[0][0].lower()

    async def test_admin_ve_lista_clientes(self, mock_telegram_update, mock_context):
        """Admin → lista de clientes."""
        update = mock_telegram_update(user_id=123456789)
        await clientes_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        text = call_args[0][0]
        assert "clientes" in text.lower()

    async def test_admin_sin_db_ve_error(self, mock_telegram_update, mock_context):
        """Admin sin DB → error."""
        update = mock_telegram_update(user_id=123456789)
        mock_context.bot_data["repository"] = None
        await clientes_command(update, mock_context)
        call_args = update.message.reply_text.call_args
        assert "no disponible" in call_args[0][0].lower()


# ── _button_crear_turno ──────────────────────────────────────────────────────


class TestButtonCrearTurno:
    """Tests para el botón 'Crear Turno'."""

    async def test_muestra_texto_ayuda(self, mock_telegram_update, mock_context):
        """Presionar 'Crear Turno' → texto de ayuda con ejemplos."""
        update = mock_telegram_update(user_id=123456789)
        result = await _button_crear_turno(update, mock_context)
        assert result == AWAITING_CREATION_INPUT
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Nuevo turno" in call_args[0][0]


# ── _button_listar_eventos ──────────────────────────────────────────────────


class TestButtonListarEventos:
    """Tests para el botón 'Listar Eventos'."""

    async def test_muestra_submenu(self, mock_telegram_update, mock_context):
        """Presionar 'Listar Eventos' → submenú con opciones de filtro."""
        update = mock_telegram_update(user_id=123456789)
        result = await _button_listar_eventos(update, mock_context)
        assert result == IDLE
        call_args = update.message.reply_text.call_args
        assert "listado" in call_args[0][0].lower()


# ── _button_editar_evento ────────────────────────────────────────────────────


class TestButtonEditarEvento:
    """Tests para el botón 'Editar Evento'."""

    async def test_muestra_lista_proximos(self, mock_telegram_update, mock_context):
        """Presionar 'Editar Evento' → lista de eventos próximos."""
        update = mock_telegram_update(user_id=123456789)
        result = await _button_editar_evento(update, mock_context)
        assert result == AWAITING_EDIT_SELECTION
        update.message.reply_text.assert_called_once()

    async def test_sin_eventos_retorna_idle(self, mock_telegram_update, mock_context):
        """Sin eventos → mensaje informativo, IDLE."""
        update = mock_telegram_update(user_id=123456789)
        orch = mock_context.bot_data["orchestrator"]
        orch._calendar.listar_proximos_eventos.return_value = []
        result = await _button_editar_evento(update, mock_context)
        assert result == IDLE


# ── _button_cancelar_evento ──────────────────────────────────────────────────


class TestButtonCancelarEvento:
    """Tests para el botón 'Cancelar Evento'."""

    async def test_admin_ve_lista_eventos(self, mock_telegram_update, mock_context):
        """Admin → lista de eventos para cancelar."""
        update = mock_telegram_update(user_id=123456789)
        result = await _button_cancelar_evento(update, mock_context)
        assert result == AWAITING_CANCEL_SELECTION

    async def test_editor_recibe_acceso_denegado(self, mock_telegram_update, mock_context):
        """Editor → acceso denegado, IDLE."""
        update = mock_telegram_update(user_id=111222333)
        result = await _button_cancelar_evento(update, mock_context)
        assert result == IDLE
        call_text = update.message.reply_text.call_args[0][0]
        assert "permiso" in call_text.lower()


# ── _cancel_selection_callback ───────────────────────────────────────────────


class TestCancelSelectionCallback:
    """Tests para la selección de evento a cancelar."""

    async def test_seleccion_valida_muestra_confirmacion(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Seleccionar evento válido → confirmación con resumen."""
        update = mock_telegram_callback_update(callback_data="select_event:1")
        mock_context.user_data["eventos_seleccion"] = [evento_proximo]

        result = await _cancel_selection_callback(update, mock_context)
        assert result == AWAITING_CANCEL_CONFIRM
        call_args = update.callback_query.edit_message_text.call_args
        assert "Cancelar" in call_args[0][0]

    async def test_seleccion_fuera_de_rango(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Número fuera de rango → mensaje de error, mismo estado."""
        update = mock_telegram_callback_update(callback_data="select_event:5")
        mock_context.user_data["eventos_seleccion"] = [evento_proximo]

        result = await _cancel_selection_callback(update, mock_context)
        assert result == AWAITING_CANCEL_SELECTION
        call_args = update.callback_query.edit_message_text.call_args
        assert "fuera de rango" in call_args[0][0].lower()

    async def test_callback_invalido_no_avanza(self, mock_telegram_callback_update, mock_context):
        """Callback que no empieza con 'select_event:' → no avanza."""
        update = mock_telegram_callback_update(callback_data="other_data")
        result = await _cancel_selection_callback(update, mock_context)
        assert result == AWAITING_CANCEL_SELECTION


# ── _cancel_confirm_callback ─────────────────────────────────────────────────


class TestCancelConfirmCallback:
    """Tests para la confirmación de cancelación."""

    async def test_confirm_elimina_evento(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Confirm → evento eliminado vía calendar_client."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_cancelar"] = evento_proximo

        result = await _cancel_confirm_callback(update, mock_context)
        assert result == IDLE
        mock_context.bot_data["calendar_client"].eliminar_evento.assert_called_once_with(
            "evt_test_1"
        )
        call_args = update.callback_query.edit_message_text.call_args
        assert "cancelado" in call_args[0][0].lower()

    async def test_cancel_no_elimina(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Cancel → evento no eliminado."""
        update = mock_telegram_callback_update(callback_data="cancel")
        mock_context.user_data["evento_a_cancelar"] = evento_proximo

        result = await _cancel_confirm_callback(update, mock_context)
        assert result == IDLE
        mock_context.bot_data["calendar_client"].eliminar_evento.assert_not_called()

    async def test_confirm_error_calendar_maneja_excepcion(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Error en Calendar → mensaje de error, sin excepción no manejada."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_cancelar"] = evento_proximo
        mock_context.bot_data["calendar_client"].eliminar_evento.side_effect = Exception(
            "API error"
        )

        result = await _cancel_confirm_callback(update, mock_context)
        assert result == IDLE
        call_args = update.callback_query.edit_message_text.call_args
        assert "error" in call_args[0][0].lower()


# ── _edit_selection_callback ─────────────────────────────────────────────────


class TestEditSelectionCallback:
    """Tests para la selección de evento a editar."""

    async def test_seleccion_valida_pide_instruccion(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Seleccionar evento → pide instrucción de edición."""
        update = mock_telegram_callback_update(callback_data="select_event:1")
        mock_context.user_data["eventos_seleccion"] = [evento_proximo]

        result = await _edit_selection_callback(update, mock_context)
        assert result == AWAITING_EDIT_INSTRUCTION
        call_args = update.callback_query.edit_message_text.call_args
        assert "seleccionado" in call_args[0][0].lower()

    async def test_seleccion_fuera_de_rango(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Número fuera de rango → error, mismo estado."""
        update = mock_telegram_callback_update(callback_data="select_event:99")
        mock_context.user_data["eventos_seleccion"] = [evento_proximo]

        result = await _edit_selection_callback(update, mock_context)
        assert result == AWAITING_EDIT_SELECTION

    async def test_callback_invalido_no_avanza(self, mock_telegram_callback_update, mock_context):
        """Callback inválido → no avanza estado."""
        update = mock_telegram_callback_update(callback_data="invalid")
        result = await _edit_selection_callback(update, mock_context)
        assert result == AWAITING_EDIT_SELECTION


# ── _edit_confirm_callback ───────────────────────────────────────────────────


class TestEditConfirmCallback:
    """Tests para la confirmación de edición."""

    async def test_cancel_no_aplica_cambios(self, mock_telegram_callback_update, mock_context):
        """Cancel → no aplica cambios."""
        update = mock_telegram_callback_update(callback_data="cancel")
        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        mock_context.bot_data["calendar_client"].actualizar_evento.assert_not_called()


# ── _confirmation_callback (flujo creación) ──────────────────────────────────


class TestConfirmationCallback:
    """Tests para la confirmación del flujo de creación."""

    async def test_cancel_no_crea_evento(self, mock_telegram_callback_update, mock_context):
        """Cancel → creación cancelada, IDLE."""
        update = mock_telegram_callback_update(callback_data="cancel")
        result = await _confirmation_callback(update, mock_context)
        assert result == IDLE
        call_args = update.callback_query.edit_message_text.call_args
        assert "cancelada" in call_args[0][0].lower()


# ── _send_orchestrator_response ──────────────────────────────────────────────


class TestSendOrchestratorResponse:
    """Tests para el helper de envío de respuesta."""

    async def test_envia_texto(self, mock_telegram_update, mock_context):
        """Envía texto de OrchestratorResponse."""
        update = mock_telegram_update()
        response = OrchestratorResponse(text="Hola", next_state=IDLE)
        result = await _send_orchestrator_response(update, mock_context, response)
        assert result == IDLE
        update.effective_chat.send_message.assert_called_once()

    async def test_guarda_contexto(self, mock_telegram_update, mock_context):
        """Si hay context, lo guarda en user_data."""
        update = mock_telegram_update()
        ctx = {"nombre_cliente": "García"}
        response = OrchestratorResponse(text="Ok", context=ctx, next_state=IDLE)
        await _send_orchestrator_response(update, mock_context, response)
        assert mock_context.user_data["creation_context"] == ctx

    async def test_callback_usa_edit_message(self, mock_telegram_callback_update, mock_context):
        """Con is_callback=True, usa edit_message_text."""
        update = mock_telegram_callback_update()
        response = OrchestratorResponse(text="Ok", next_state=IDLE)
        await _send_orchestrator_response(update, mock_context, response, is_callback=True)
        update.callback_query.edit_message_text.assert_called_once()

    async def test_retorna_idle_si_next_state_none(self, mock_telegram_update, mock_context):
        """Si next_state es None → retorna IDLE."""
        update = mock_telegram_update()
        response = OrchestratorResponse(text="Ok", next_state=None)
        result = await _send_orchestrator_response(update, mock_context, response)
        assert result == IDLE

    async def test_guarda_eventos_seleccion_en_user_data(self, mock_telegram_update, mock_context):
        """Si context tiene eventos_seleccion → guarda en user_data['eventos_seleccion'] (Issue 4)."""
        update = mock_telegram_update()
        eventos = [{"id": "evt1", "summary": "Instalación"}]
        ctx = {"eventos_seleccion": eventos}
        response = OrchestratorResponse(
            text="Seleccioná un evento:", context=ctx, next_state=AWAITING_CANCEL_SELECTION
        )
        result = await _send_orchestrator_response(update, mock_context, response)
        assert result == AWAITING_CANCEL_SELECTION
        assert mock_context.user_data["eventos_seleccion"] == eventos
        # No debe guardar en creation_context
        assert "creation_context" not in mock_context.user_data


# ── _timeout_handler ─────────────────────────────────────────────────────────


class TestTimeoutHandler:
    """Tests para el timeout del ConversationHandler."""

    async def test_envia_mensaje_timeout(self, mock_telegram_update, mock_context):
        """Timeout → mensaje de timeout + limpia user_data."""
        update = mock_telegram_update(user_id=123456789)
        result = await _timeout_handler(update, mock_context)
        from telegram.ext import ConversationHandler

        assert result == ConversationHandler.END
        assert mock_context.user_data == {}


# ── build_conversation_handler ───────────────────────────────────────────────


class TestBuildConversationHandler:
    """Tests para build_conversation_handler()."""

    def test_retorna_conversation_handler(self, mock_settings):
        """Retorna un ConversationHandler configurado."""
        from telegram.ext import ConversationHandler

        handler = build_conversation_handler(mock_settings)
        assert isinstance(handler, ConversationHandler)

    def test_tiene_entry_points(self, mock_settings):
        """Tiene entry points definidos."""
        handler = build_conversation_handler(mock_settings)
        assert len(handler.entry_points) > 0

    def test_tiene_estados(self, mock_settings):
        """Tiene estados definidos."""
        handler = build_conversation_handler(mock_settings)
        assert len(handler.states) > 0

    def test_tiene_timeout(self, mock_settings):
        """Timeout de 5 minutos (300s)."""
        handler = build_conversation_handler(mock_settings)
        assert handler.conversation_timeout == 300

    def test_tiene_fallbacks(self, mock_settings):
        """Tiene fallbacks (/start)."""
        handler = build_conversation_handler(mock_settings)
        assert len(handler.fallbacks) > 0

    def test_idle_en_states(self, mock_settings):
        """IDLE está incluido en el dict de states (Issue 2: evita que la conversación se atasque)."""
        handler = build_conversation_handler(mock_settings)
        assert IDLE in handler.states
        assert len(handler.states[IDLE]) > 0

    def test_timeout_en_states(self, mock_settings):
        """ConversationHandler.TIMEOUT está registrado en states (Issue 1)."""
        from telegram.ext import ConversationHandler as CH

        handler = build_conversation_handler(mock_settings)
        assert CH.TIMEOUT in handler.states
        assert len(handler.states[CH.TIMEOUT]) > 0

    def test_awaiting_client_name_en_states(self, mock_settings):
        """AWAITING_CLIENT_NAME está incluido en states."""
        handler = build_conversation_handler(mock_settings)
        assert AWAITING_CLIENT_NAME in handler.states


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 5 — Handler refactors: cancel/edit usan orchestrator
# ══════════════════════════════════════════════════════════════════════════════


class TestCancelConfirmUsesOrchestrator:
    """Tests para verificar que _cancel_confirm_callback delega al orchestrator."""

    async def test_confirm_usa_orchestrator_confirm_cancel(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Confirm → orchestrator.confirm_cancel() es llamado."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_cancelar"] = evento_proximo

        orchestrator = mock_context.bot_data["orchestrator"]
        # Espiar confirm_cancel
        orchestrator.confirm_cancel = AsyncMock(
            return_value=OrchestratorResponse(
                text="✅ Evento cancelado exitosamente.", next_state=IDLE
            )
        )

        result = await _cancel_confirm_callback(update, mock_context)
        assert result == IDLE
        orchestrator.confirm_cancel.assert_called_once_with("evt_test_1")
        call_args = update.callback_query.edit_message_text.call_args
        assert "cancelado" in call_args[0][0].lower()

    async def test_confirm_sin_event_id_muestra_error(
        self, mock_telegram_callback_update, mock_context
    ):
        """Si evento no tiene id → mensaje de error."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_cancelar"] = {}  # Sin id

        result = await _cancel_confirm_callback(update, mock_context)
        assert result == IDLE
        call_args = update.callback_query.edit_message_text.call_args
        assert "no se encontró" in call_args[0][0].lower()


class TestEditInstructionUsesOrchestrator:
    """Tests para verificar que _edit_instruction_handler delega al orchestrator."""

    async def test_instruccion_llama_parse_and_preview(
        self, mock_telegram_update, mock_context, evento_proximo
    ):
        """Texto en AWAITING_EDIT_INSTRUCTION → parse_and_preview_edit llamado."""
        update = mock_telegram_update(text="pasalo para el viernes a las 16")
        mock_context.user_data["evento_a_editar"] = evento_proximo

        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.parse_and_preview_edit = AsyncMock(
            return_value=OrchestratorResponse(
                text="✏️ *Cambios a aplicar:*\n\nFecha: 2026-03-06\n\n¿Confirmar?",
                keyboard=MagicMock(),
                context={"edit_instruction": {}, "patch": {"start": {}}},
                next_state=AWAITING_EDIT_CONFIRM,
            )
        )

        result = await _edit_instruction_handler(update, mock_context)
        assert result == AWAITING_EDIT_CONFIRM
        orchestrator.parse_and_preview_edit.assert_called_once_with(
            instruccion="pasalo para el viernes a las 16",
            evento_actual=evento_proximo,
        )
        # Verifica que el patch se guardó en user_data
        assert "patch" in mock_context.user_data

    async def test_instruccion_error_retorna_edit_instruction(
        self, mock_telegram_update, mock_context, evento_proximo
    ):
        """Error en parse_and_preview → mensaje de error, permanece en AWAITING_EDIT_INSTRUCTION."""
        update = mock_telegram_update(text="cambio ininteligible")
        mock_context.user_data["evento_a_editar"] = evento_proximo

        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.parse_and_preview_edit = AsyncMock(side_effect=Exception("Parse error"))

        result = await _edit_instruction_handler(update, mock_context)
        assert result == AWAITING_EDIT_INSTRUCTION
        call_args = update.message.reply_text.call_args_list[-1]
        assert "no pude interpretar" in call_args[0][0].lower()


class TestEditConfirmUsesOrchestrator:
    """Tests para verificar que _edit_confirm_callback delega al orchestrator."""

    async def test_confirm_usa_orchestrator_confirm_edit(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Confirm → orchestrator.confirm_edit() es llamado con patch correcto."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_editar"] = evento_proximo
        mock_context.user_data["patch"] = {"location": "Av. Libertador 1234"}

        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.confirm_edit = AsyncMock(
            return_value=OrchestratorResponse(
                text="✅ Evento actualizado exitosamente.", next_state=IDLE
            )
        )

        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        orchestrator.confirm_edit.assert_called_once_with(
            "evt_test_1", {"location": "Av. Libertador 1234"}, nuevo_tipo_trabajo=None
        )
        call_args = update.callback_query.edit_message_text.call_args
        assert "actualizado" in call_args[0][0].lower()

    async def test_cancel_no_aplica_cambios_ni_llama_orchestrator(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Cancel → no aplica cambios, no llama confirm_edit."""
        update = mock_telegram_callback_update(callback_data="cancel")
        mock_context.user_data["evento_a_editar"] = evento_proximo
        mock_context.user_data["patch"] = {"location": "x"}

        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.confirm_edit = AsyncMock()

        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        orchestrator.confirm_edit.assert_not_called()
        call_args = update.callback_query.edit_message_text.call_args
        assert (
            "cancelada" in call_args[0][0].lower() or "no fue modificado" in call_args[0][0].lower()
        )


# ══════════════════════════════════════════════════════════════════════════════
# _awaiting_client_name_handler
# ══════════════════════════════════════════════════════════════════════════════


class TestEditConfirmSinEventId:
    """Tests para _edit_confirm_callback sin event_id (Issue 10)."""

    async def test_confirm_sin_event_id_muestra_error(
        self, mock_telegram_callback_update, mock_context
    ):
        """Si evento_a_editar no tiene id → mensaje de error."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_editar"] = {}  # Sin id

        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        call_args = update.callback_query.edit_message_text.call_args
        assert "no se encontró" in call_args[0][0].lower()

    async def test_confirm_sin_evento_a_editar_muestra_error(
        self, mock_telegram_callback_update, mock_context
    ):
        """Si no hay evento_a_editar en user_data → mensaje de error."""
        update = mock_telegram_callback_update(callback_data="confirm")
        # user_data vacío — no tiene "evento_a_editar"

        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        call_args = update.callback_query.edit_message_text.call_args
        assert "no se encontró" in call_args[0][0].lower()


class TestAwaitingClientNameHandler:
    """Tests para _awaiting_client_name_handler."""

    async def test_nombre_valido_busca_y_retorna_idle(self, mock_telegram_update, mock_context):
        """Nombre válido → listar_por_cliente + IDLE."""
        update = mock_telegram_update(text="García")
        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.listar_por_cliente = AsyncMock(
            return_value="👤 *Turnos de García, Juan:*\n\n*Próximos:*\nNo hay turnos próximos."
        )

        result = await _awaiting_client_name_handler(update, mock_context)
        assert result == IDLE
        orchestrator.listar_por_cliente.assert_called_once_with("García")
        # Verifica que se envió el resultado
        calls = update.message.reply_text.call_args_list
        assert any("García" in str(c) for c in calls)

    async def test_nombre_vacio_repregunta(self, mock_telegram_update, mock_context):
        """Nombre vacío → repregunta y queda en AWAITING_CLIENT_NAME."""
        update = mock_telegram_update(text="   ")

        result = await _awaiting_client_name_handler(update, mock_context)
        assert result == AWAITING_CLIENT_NAME
        call_args = update.message.reply_text.call_args
        assert "nombre" in call_args[0][0].lower()

    async def test_confirm_edit_con_tipo_servicio_pasa_tipo(
        self, mock_telegram_callback_update, mock_context, evento_proximo
    ):
        """Confirm con edit_instruction que tiene nuevo_tipo_servicio → lo pasa a confirm_edit."""
        update = mock_telegram_callback_update(callback_data="confirm")
        mock_context.user_data["evento_a_editar"] = evento_proximo
        mock_context.user_data["patch"] = {"colorId": "9"}
        mock_context.user_data["edit_instruction"] = {"nuevo_tipo_servicio": "instalacion"}

        orchestrator = mock_context.bot_data["orchestrator"]
        orchestrator.confirm_edit = AsyncMock(
            return_value=OrchestratorResponse(
                text="✅ Evento actualizado exitosamente.", next_state=IDLE
            )
        )

        result = await _edit_confirm_callback(update, mock_context)
        assert result == IDLE
        orchestrator.confirm_edit.assert_called_once_with(
            "evt_test_1", {"colorId": "9"}, nuevo_tipo_trabajo="instalacion"
        )
