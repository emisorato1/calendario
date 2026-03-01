"""ConversationHandler de Telegram: estados, flujos y timeout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from agents.telegram_listener.commands import (
    clientes_command,
    help_command,
    start_command,
    status_command,
)
from agents.telegram_listener.filters import AdminOnlyFilter, AuthorizedUserFilter
from agents.telegram_listener.keyboards import (
    CONFIRM_KEYBOARD,
    build_event_selection_keyboard,
    build_list_submenu_keyboard,
    get_main_menu,
)
from core.logger import get_logger
from core.orchestrator import (
    AWAITING_CANCEL_CONFIRM,
    AWAITING_CANCEL_SELECTION,
    AWAITING_CONFIRMATION,
    AWAITING_CREATION_INPUT,
    AWAITING_EDIT_CONFIRM,
    AWAITING_EDIT_INSTRUCTION,
    AWAITING_EDIT_SELECTION,
    AWAITING_MISSING_DATA,
    IDLE,
    CreationContext,
    Orchestrator,
    OrchestratorResponse,
)

if TYPE_CHECKING:
    from config.settings import Settings

log = get_logger(__name__)

# Textos constantes
CREATION_HELP_TEXT = (
    "📅 *Nuevo turno*\n\n"
    "Contáme sobre el turno que querés agendar.\n"
    "Podés escribir de forma natural, por ejemplo:\n\n"
    '• "Instalación de cámaras en lo de García el lunes a las 10"\n'
    '• "Revisión en casa de López, mañana 14:00"\n'
    '• "Presupuesto para Martínez, viernes 9:30"\n\n'
    "💡 Cuanto más detallés (cliente, servicio, fecha, hora), más rápido lo proceso."
)

TIMEOUT_TEXT = "⏰ Se agotó el tiempo de espera. Volvemos al menú principal."
ACCESS_DENIED_TEXT = (
    "No tenés permiso para realizar esa acción. Podés editar eventos y consultar la agenda."
)


# ── Handler functions ────────────────────────────────────────────────────────


async def _button_crear_turno(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Botón '📅 Crear Turno' presionado por Admin."""
    await update.message.reply_text(CREATION_HELP_TEXT, parse_mode="Markdown")
    return AWAITING_CREATION_INPUT


async def _button_listar_eventos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Botón '📋 Listar Eventos' presionado."""
    keyboard = build_list_submenu_keyboard()
    await update.message.reply_text(
        "📋 *¿Qué tipo de listado necesitás?*",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return IDLE


async def _button_editar_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Botón '✏️ Editar Evento' presionado."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    eventos, text = await orchestrator.get_upcoming_events_for_selection()

    if not eventos:
        await update.message.reply_text(text)
        return IDLE

    context.user_data["eventos_seleccion"] = eventos
    keyboard = build_event_selection_keyboard(eventos)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return AWAITING_EDIT_SELECTION


async def _button_cancelar_evento(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Botón '🚫 Cancelar Evento' presionado por Admin."""
    settings: Settings = context.bot_data["settings"]
    user_id = update.effective_user.id

    if not settings.is_admin(user_id):
        await update.message.reply_text(ACCESS_DENIED_TEXT)
        return IDLE

    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    eventos, text = await orchestrator.get_upcoming_events_for_selection()

    if not eventos:
        await update.message.reply_text(text)
        return IDLE

    context.user_data["eventos_seleccion"] = eventos
    keyboard = build_event_selection_keyboard(eventos)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return AWAITING_CANCEL_SELECTION


async def _awaiting_creation_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe texto libre en AWAITING_CREATION_INPUT."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]

    await update.message.reply_text("⏳ Procesando...")

    from agents.groq_parser.parser import parse_message

    parsed = await parse_message(
        update.message.text,
        context.bot_data["groq_client"],
    )

    response = await orchestrator.start_creation_flow(parsed)
    return await _send_orchestrator_response(update, context, response)


async def _awaiting_missing_data_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe texto libre en AWAITING_MISSING_DATA."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    ctx_data = context.user_data.get("creation_context", {})
    campo = ctx_data.get("campo_pendiente", "hora")

    response = await orchestrator.complete_missing_field(
        field_name=campo,
        value=update.message.text,
        context_data=ctx_data,
    )
    return await _send_orchestrator_response(update, context, response)


async def _awaiting_missing_data_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de botones en AWAITING_MISSING_DATA."""
    query = update.callback_query
    await query.answer()
    data = query.data

    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    ctx_data = context.user_data.get("creation_context", {})

    if data.startswith("time_slot:"):
        hora_str = data.split(":", 1)[1]
        response = await orchestrator.complete_missing_field(
            field_name="hora",
            value=hora_str,
            context_data=ctx_data,
        )
    elif data.startswith("date:"):
        fecha_str = data.split(":", 1)[1]
        response = await orchestrator.complete_missing_field(
            field_name="fecha",
            value=fecha_str,
            context_data=ctx_data,
        )
    elif data == "other_time":
        await query.edit_message_text(
            "⌨️ Escribí el horario que necesitás (ej: 17:30, cinco de la tarde):"
        )
        ctx_data["campo_pendiente"] = "hora"
        context.user_data["creation_context"] = ctx_data
        return AWAITING_MISSING_DATA
    elif data == "other_date":
        await query.edit_message_text(
            "⌨️ Escribí la fecha que necesitás (ej: martes, 15/03, próximo viernes):"
        )
        ctx_data["campo_pendiente"] = "fecha"
        context.user_data["creation_context"] = ctx_data
        return AWAITING_MISSING_DATA
    elif data == "choose_other_day":
        from agents.telegram_listener.keyboards import build_date_suggestion_keyboard

        await query.edit_message_text(
            "📅 Elegí otra fecha:",
            reply_markup=build_date_suggestion_keyboard(),
        )
        ctx_data["campo_pendiente"] = "fecha"
        ctx_data["fecha"] = None
        context.user_data["creation_context"] = ctx_data
        return AWAITING_MISSING_DATA
    elif data == "urgent_override":
        ctx_data["urgente"] = True
        context.user_data["creation_context"] = ctx_data
        # Reprocesar con urgente=True
        from agents.groq_parser.schemas import Intencion, ParsedMessage

        parsed = ParsedMessage(intencion=Intencion.agendar, urgente=True)
        response = await orchestrator.start_creation_flow(parsed, ctx_data)
    else:
        response = OrchestratorResponse(
            text="No entendí esa selección.", next_state=AWAITING_MISSING_DATA
        )

    return await _send_orchestrator_response(update, context, response, is_callback=True)


async def _confirmation_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de confirmación/cancelación en AWAITING_CONFIRMATION."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        orchestrator: Orchestrator = context.bot_data["orchestrator"]
        ctx_data = context.user_data.get("creation_context", {})

        # Reconstruir CreationContext
        ctx = CreationContext()
        for k, v in ctx_data.items():
            if k in CreationContext.__dataclass_fields__ and v is not None:
                from datetime import date, time

                if k == "fecha" and isinstance(v, str):
                    v = date.fromisoformat(v)
                elif k == "hora" and isinstance(v, str):
                    parts = v.split(":")
                    v = time(int(parts[0]), int(parts[1]))
                setattr(ctx, k, v)

        # Recuperar cliente de DB si tenemos cliente_id
        cliente_id = ctx_data.get("cliente_id")
        if cliente_id and ctx.cliente_obj is None:
            try:
                ctx.cliente_obj = await orchestrator._repo._get_cliente_by_id(cliente_id)
            except Exception:
                pass

        response = await orchestrator.confirm_event(ctx)
        await query.edit_message_text(response.text, parse_mode="Markdown")

        settings: Settings = context.bot_data["settings"]
        menu = get_main_menu(update.effective_user.id, settings)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="¿Qué más necesitás?",
            reply_markup=menu,
        )
    else:
        await query.edit_message_text("❌ Creación cancelada.")

    context.user_data.clear()
    return IDLE


async def _cancel_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de selección de evento para cancelar."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("select_event:"):
        return AWAITING_CANCEL_SELECTION

    idx = int(query.data.split(":")[1]) - 1
    eventos = context.user_data.get("eventos_seleccion", [])

    if idx < 0 or idx >= len(eventos):
        await query.edit_message_text("❌ Número fuera de rango. Intentá de nuevo.")
        return AWAITING_CANCEL_SELECTION

    evento = eventos[idx]
    context.user_data["evento_a_cancelar"] = evento

    from agents.calendar_sync.formatter import format_event_summary

    resumen = format_event_summary(evento)
    await query.edit_message_text(
        f"🚫 *¿Cancelar este evento?*\n\n{resumen}",
        reply_markup=CONFIRM_KEYBOARD,
        parse_mode="Markdown",
    )
    return AWAITING_CANCEL_CONFIRM


async def _cancel_confirm_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de confirmación de cancelación."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        evento = context.user_data.get("evento_a_cancelar", {})
        event_id = evento.get("id")

        if event_id:
            orchestrator: Orchestrator = context.bot_data["orchestrator"]
            response = await orchestrator.confirm_cancel(event_id)
            await query.edit_message_text(response.text, parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ No se encontró el evento.")
    else:
        await query.edit_message_text("Cancelación abortada. El evento no fue modificado.")

    context.user_data.clear()
    return IDLE


async def _edit_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de selección de evento para editar."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("select_event:"):
        return AWAITING_EDIT_SELECTION

    idx = int(query.data.split(":")[1]) - 1
    eventos = context.user_data.get("eventos_seleccion", [])

    if idx < 0 or idx >= len(eventos):
        await query.edit_message_text("❌ Número fuera de rango. Intentá de nuevo.")
        return AWAITING_EDIT_SELECTION

    evento = eventos[idx]
    context.user_data["evento_a_editar"] = evento

    from agents.calendar_sync.formatter import format_event_summary

    resumen = format_event_summary(evento)
    await query.edit_message_text(
        f"✏️ *Evento seleccionado:*\n\n{resumen}\n\n"
        "Escribí qué querés cambiar. Por ejemplo:\n"
        '• "Pasalo para el viernes a las 16"\n'
        '• "Cambiá el servicio a instalación"\n'
        '• "Nueva dirección: Av. Libertador 1234"',
        parse_mode="Markdown",
    )
    return AWAITING_EDIT_INSTRUCTION


async def _edit_instruction_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe instrucción de edición en texto libre."""
    await update.message.reply_text("⏳ Procesando...")

    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    evento = context.user_data.get("evento_a_editar", {})

    try:
        response = await orchestrator.parse_and_preview_edit(
            instruccion=update.message.text,
            evento_actual=evento,
        )
        # Guardar patch y edit_instruction en user_data
        if response.context:
            context.user_data["edit_instruction"] = response.context.get("edit_instruction", {})
            context.user_data["patch"] = response.context.get("patch", {})

        await update.message.reply_text(
            response.text,
            reply_markup=response.keyboard,
            parse_mode="Markdown",
        )
        return response.next_state if response.next_state is not None else AWAITING_EDIT_CONFIRM
    except Exception as exc:
        log.error("error_parse_edit", error=str(exc))
        await update.message.reply_text("❌ No pude interpretar la instrucción. Intentá de nuevo.")
        return AWAITING_EDIT_INSTRUCTION


async def _edit_confirm_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback de confirmación de edición."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        evento = context.user_data.get("evento_a_editar", {})
        patch = context.user_data.get("patch", {})
        orchestrator: Orchestrator = context.bot_data["orchestrator"]

        response = await orchestrator.confirm_edit(evento.get("id", ""), patch)
        await query.edit_message_text(response.text, parse_mode="Markdown")
    else:
        await query.edit_message_text("Edición cancelada. El evento no fue modificado.")

    context.user_data.clear()
    return IDLE


async def _idle_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Recibe texto libre en IDLE. Despacha al orquestador."""
    orchestrator: Orchestrator = context.bot_data["orchestrator"]
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Procesando...")

    response = await orchestrator.process_message(update.message.text, user_id)
    return await _send_orchestrator_response(update, context, response)


async def _list_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Callback del submenú de listado."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("list:"):
        return IDLE

    tipo = query.data.split(":", 1)[1]
    orchestrator: Orchestrator = context.bot_data["orchestrator"]

    from agents.groq_parser.schemas import Intencion, ParsedMessage

    intencion_map = {
        "pendientes": Intencion.listar_pendientes,
        "dia": Intencion.listar_dia,
        "cliente": Intencion.listar_cliente,
        "historial": Intencion.listar_historial,
    }
    intencion = intencion_map.get(tipo, Intencion.listar_pendientes)
    parsed = ParsedMessage(intencion=intencion)

    response = await orchestrator.resolve_list_query(parsed)
    await query.edit_message_text(response.text, parse_mode="Markdown")
    return IDLE


async def _timeout_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handler de timeout del ConversationHandler."""
    if update and update.effective_chat:
        settings: Settings = context.bot_data["settings"]
        user_id = update.effective_user.id if update.effective_user else 0
        menu = get_main_menu(user_id, settings)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=TIMEOUT_TEXT,
            reply_markup=menu,
        )
    context.user_data.clear()
    log.info("conversation_timeout")
    return ConversationHandler.END


# ── Helper ───────────────────────────────────────────────────────────────────


async def _send_orchestrator_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    response: OrchestratorResponse,
    is_callback: bool = False,
) -> int:
    """Envía la respuesta del orquestador al usuario."""
    # Guardar contexto si lo hay
    if response.context:
        context.user_data["creation_context"] = response.context

    # Enviar mensaje
    if is_callback and update.callback_query:
        await update.callback_query.edit_message_text(
            response.text,
            reply_markup=response.keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.effective_chat.send_message(
            response.text,
            reply_markup=response.keyboard,
            parse_mode="Markdown",
        )

    return response.next_state if response.next_state is not None else IDLE


# ── Builder ──────────────────────────────────────────────────────────────────


def build_conversation_handler(settings: Settings) -> ConversationHandler:
    """Construye el ConversationHandler completo con todos los estados.

    Args:
        settings: Instancia de Settings para los filtros.

    Returns:
        ConversationHandler configurado.
    """
    authorized = AuthorizedUserFilter(settings)
    admin_only = AdminOnlyFilter(settings)

    return ConversationHandler(
        entry_points=[
            # Botones del menú principal
            MessageHandler(
                authorized & filters.Regex(r"^📅 Crear Turno$"),
                _button_crear_turno,
            ),
            MessageHandler(
                authorized & filters.Regex(r"^📋 Listar Eventos$"),
                _button_listar_eventos,
            ),
            MessageHandler(
                authorized & filters.Regex(r"^✏️ Editar Evento$"),
                _button_editar_evento,
            ),
            MessageHandler(
                authorized & filters.Regex(r"^🚫 Cancelar Evento$"),
                _button_cancelar_evento,
            ),
            # Texto libre en IDLE
            MessageHandler(
                authorized & filters.TEXT & ~filters.COMMAND,
                _idle_text_handler,
            ),
            # Callbacks del submenú de listado
            CallbackQueryHandler(_list_callback_handler, pattern=r"^list:"),
        ],
        states={
            AWAITING_CREATION_INPUT: [
                MessageHandler(
                    authorized & filters.TEXT & ~filters.COMMAND,
                    _awaiting_creation_input,
                ),
            ],
            AWAITING_MISSING_DATA: [
                CallbackQueryHandler(
                    _awaiting_missing_data_callback,
                    pattern=r"^(time_slot:|date:|other_time|other_date|choose_other_day|urgent_override)",
                ),
                MessageHandler(
                    authorized & filters.TEXT & ~filters.COMMAND,
                    _awaiting_missing_data_text,
                ),
            ],
            AWAITING_CONFIRMATION: [
                CallbackQueryHandler(
                    _confirmation_callback,
                    pattern=r"^(confirm|cancel)$",
                ),
            ],
            AWAITING_CANCEL_SELECTION: [
                CallbackQueryHandler(
                    _cancel_selection_callback,
                    pattern=r"^select_event:",
                ),
            ],
            AWAITING_CANCEL_CONFIRM: [
                CallbackQueryHandler(
                    _cancel_confirm_callback,
                    pattern=r"^(confirm|cancel)$",
                ),
            ],
            AWAITING_EDIT_SELECTION: [
                CallbackQueryHandler(
                    _edit_selection_callback,
                    pattern=r"^select_event:",
                ),
            ],
            AWAITING_EDIT_INSTRUCTION: [
                MessageHandler(
                    authorized & filters.TEXT & ~filters.COMMAND,
                    _edit_instruction_handler,
                ),
            ],
            AWAITING_EDIT_CONFIRM: [
                CallbackQueryHandler(
                    _edit_confirm_callback,
                    pattern=r"^(confirm|cancel)$",
                ),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
        ],
        conversation_timeout=300,  # 5 minutos
        name="main_conversation",
        persistent=False,
    )
