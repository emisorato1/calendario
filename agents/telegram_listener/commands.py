"""Handlers de comandos de Telegram: /start, /help, /status, /clientes."""

from __future__ import annotations

import time as time_mod
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from agents.telegram_listener.keyboards import get_main_menu
from core.logger import get_logger

if TYPE_CHECKING:
    from agents.calendar_sync.client import CalendarClient
    from agents.db_manager.repository import DBRepository
    from agents.groq_parser.client import GroqClient
    from config.settings import Settings

log = get_logger(__name__)

# Referencia al tiempo de inicio para calcular uptime
_START_TIME: float = time_mod.monotonic()


def reset_start_time() -> None:
    """Resetea el tiempo de inicio (útil para tests)."""
    global _START_TIME
    _START_TIME = time_mod.monotonic()


def _format_uptime(seconds: float) -> str:
    """Formatea segundos en un string legible."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para /start. Bienvenida + menú según rol.

    Roles: Admin + Editor.
    """
    settings: Settings = context.bot_data["settings"]
    user_id = update.effective_user.id
    nombre = update.effective_user.first_name or "usuario"

    menu = get_main_menu(user_id, settings)

    if settings.is_admin(user_id):
        text = (
            f"👋 ¡Hola {nombre}! Soy tu asistente de agenda.\n\n"
            "Podés usar los botones del menú o escribirme de forma natural.\n\n"
            "📅 Crear, editar, cancelar y consultar eventos.\n"
            "👤 Gestionar clientes.\n"
            "📊 Ver el estado del sistema con /status."
        )
    else:
        text = (
            f"👋 ¡Hola {nombre}! Soy tu asistente de agenda.\n\n"
            "Podés usar los botones del menú o escribirme de forma natural.\n\n"
            "✏️ Editar eventos y consultar la agenda."
        )

    await update.message.reply_text(text, reply_markup=menu)
    log.info(
        "start_command", user_id=user_id, role="admin" if settings.is_admin(user_id) else "editor"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para /help. Lista capacidades según rol.

    Roles: Admin + Editor.
    """
    settings: Settings = context.bot_data["settings"]
    user_id = update.effective_user.id

    if settings.is_admin(user_id):
        text = (
            "📖 *Ayuda — Admin*\n\n"
            "Podés hacer lo siguiente:\n\n"
            "📅 *Crear Turno* — Agendar un nuevo evento\n"
            "📋 *Listar Eventos* — Ver eventos pendientes, por día o por cliente\n"
            "✏️ *Editar Evento* — Modificar un evento existente\n"
            "🚫 *Cancelar Evento* — Eliminar un evento\n\n"
            "*Comandos:*\n"
            "/start — Reiniciar el menú\n"
            "/help — Esta ayuda\n"
            "/status — Estado del sistema\n"
            "/clientes — Últimos 10 clientes\n\n"
            "💡 También podés escribir de forma natural:\n"
            '_"Agendá una instalación para García el martes a las 10"_'
        )
    else:
        text = (
            "📖 *Ayuda — Editor*\n\n"
            "Podés hacer lo siguiente:\n\n"
            "📋 *Listar Eventos* — Ver eventos pendientes, por día o por cliente\n"
            "✏️ *Editar Evento* — Modificar un evento existente\n\n"
            "*Comandos:*\n"
            "/start — Reiniciar el menú\n"
            "/help — Esta ayuda\n\n"
            "💡 También podés escribir de forma natural:\n"
            '_"¿Qué hay agendado para mañana?"_'
        )

    await update.message.reply_text(text, parse_mode="Markdown")
    log.info("help_command", user_id=user_id)


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para /status. Estado real: DB, Calendar, Groq, uptime.

    Roles: Solo Admin.
    """
    settings: Settings = context.bot_data["settings"]
    user_id = update.effective_user.id

    if not settings.is_admin(user_id):
        await update.message.reply_text("⛔ Este comando es solo para administradores.")
        return

    uptime = _format_uptime(time_mod.monotonic() - _START_TIME)
    results: list[str] = [f"📊 *Estado del Sistema*\n\n⏱️ Uptime: {uptime}\n"]

    # DB check
    repository: DBRepository = context.bot_data.get("repository")
    if repository:
        try:
            await repository._conn.execute("SELECT 1")
            results.append("🟢 Base de datos: OK")
        except Exception as exc:
            results.append(f"🔴 Base de datos: Error — {exc}")
    else:
        results.append("🟡 Base de datos: No configurada")

    # Calendar check
    calendar_client: CalendarClient = context.bot_data.get("calendar_client")
    if calendar_client:
        try:
            await calendar_client.listar_proximos_eventos(n=1)
            results.append("🟢 Google Calendar: OK")
        except Exception as exc:
            results.append(f"🔴 Google Calendar: Error — {exc}")
    else:
        results.append("🟡 Google Calendar: No configurado")

    # Groq check
    groq_client: GroqClient = context.bot_data.get("groq_client")
    if groq_client:
        try:
            from pydantic import BaseModel

            class PingResponse(BaseModel):
                response: str

            await groq_client.call(
                system_prompt="ping",
                user_prompt="respond with 'pong'",
                response_format=PingResponse,
            )
            results.append("🟢 Groq API: OK")
        except Exception as exc:
            results.append(f"🔴 Groq API: Error — {exc}")
    else:
        results.append("🟡 Groq API: No configurado")

    await update.message.reply_text("\n".join(results), parse_mode="Markdown")
    log.info("status_command", user_id=user_id)


async def clientes_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para /clientes. Últimos 10 clientes.

    Roles: Solo Admin.
    """
    settings: Settings = context.bot_data["settings"]
    user_id = update.effective_user.id

    if not settings.is_admin(user_id):
        await update.message.reply_text("⛔ Este comando es solo para administradores.")
        return

    repository: DBRepository = context.bot_data.get("repository")
    if not repository:
        await update.message.reply_text("❌ Base de datos no disponible.")
        return

    try:
        clientes = await repository.listar_clientes(limit=10)
    except Exception as exc:
        log.error("error_listar_clientes", error=str(exc))
        await update.message.reply_text("❌ Error al consultar la base de datos.")
        return

    if not clientes:
        await update.message.reply_text("No hay clientes registrados todavía.")
        return

    lines = ["👥 *Últimos 10 clientes:*\n"]
    for i, cliente in enumerate(clientes, 1):
        tel = cliente.telefono or "Sin teléfono"
        fecha = ""
        if cliente.fecha_alta:
            if isinstance(cliente.fecha_alta, str):
                fecha = cliente.fecha_alta[:10]
            else:
                fecha = cliente.fecha_alta.strftime("%d/%m/%Y")
        lines.append(f"{i}. *{cliente.nombre_completo}* — {tel} — Alta: {fecha}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    log.info("clientes_command", user_id=user_id, total=len(clientes))
