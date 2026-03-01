"""Teclados de Telegram: menús fijos y teclados dinámicos."""

from __future__ import annotations

from datetime import date, timedelta, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from config.settings import Settings
from core.work_schedule import get_available_slots


# ── Menús Principales (ReplyKeyboard persistente) ────────────────────────────

ADMIN_MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["📅 Crear Turno", "📋 Listar Eventos"],
        ["✏️ Editar Evento", "🚫 Cancelar Evento"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

EDITOR_MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["✏️ Editar Evento", "📋 Listar Eventos"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


# ── Teclado de Confirmación (InlineKeyboard) ─────────────────────────────────

CONFIRM_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ]
    ]
)


# ── Funciones de conveniencia ─────────────────────────────────────────────────


def get_main_menu(user_id: int, settings: Settings) -> ReplyKeyboardMarkup:
    """Retorna el menú correcto según el rol del usuario.

    Args:
        user_id: ID de Telegram del usuario.
        settings: Instancia de Settings.

    Returns:
        ADMIN_MAIN_MENU si es admin, EDITOR_MAIN_MENU en caso contrario.
    """
    if settings.is_admin(user_id):
        return ADMIN_MAIN_MENU
    return EDITOR_MAIN_MENU


# ── Teclados Dinámicos ───────────────────────────────────────────────────────


def build_time_slot_keyboard(
    fecha: date,
    duracion_horas: float,
    settings: Settings,
    eventos_del_dia: list[dict],
) -> InlineKeyboardMarkup:
    """Genera botones de RANGOS horarios disponibles para el día dado.

    Cada botón muestra: 'HH:MM - HH:MM' (inicio - fin según duración).
    Agrega botón '¿Otro horario?' al final.

    Args:
        fecha: Fecha del día.
        duracion_horas: Duración del servicio en horas.
        settings: Instancia de Settings.
        eventos_del_dia: Lista de eventos existentes del día.

    Returns:
        InlineKeyboardMarkup con los rangos disponibles.
    """
    slots = get_available_slots(
        fecha=fecha,
        duracion_horas=duracion_horas,
        eventos_del_dia=eventos_del_dia,
        buffer_minutes=settings.conflict_buffer_minutes,
    )

    # Construir filas de 2 botones
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for slot_start, slot_end in slots:
        label = f"{slot_start.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}"
        callback = f"time_slot:{slot_start.strftime('%H:%M')}"
        row.append(InlineKeyboardButton(label, callback_data=callback))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Botón de texto libre
    buttons.append([InlineKeyboardButton("¿Otro horario?", callback_data="other_time")])

    return InlineKeyboardMarkup(buttons)


def build_day_full_keyboard(fecha: date) -> InlineKeyboardMarkup:
    """Teclado para cuando el día está completamente lleno.

    Args:
        fecha: Fecha del día lleno.

    Returns:
        InlineKeyboardMarkup con opciones de otro día o urgente.
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Elegir otro día", callback_data="choose_other_day")],
            [
                InlineKeyboardButton(
                    "🚨 Es urgente — agendar igual",
                    callback_data="urgent_override",
                )
            ],
        ]
    )


def build_date_suggestion_keyboard() -> InlineKeyboardMarkup:
    """Genera botones de fechas rápidas cuando falta la fecha.

    Muestra: Hoy, Mañana, Sábado (próximo), Próximo Lunes, ¿Otra fecha?

    Returns:
        InlineKeyboardMarkup con sugerencias de fecha.
    """
    today = date.today()

    # Calcular próximo sábado
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0:
        days_until_saturday = 7  # Si hoy es sábado, próximo sábado
    proximo_sabado = today + timedelta(days=days_until_saturday)

    # Calcular próximo lunes
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # Si hoy es lunes, próximo lunes
    proximo_lunes = today + timedelta(days=days_until_monday)

    manana = today + timedelta(days=1)

    buttons = [
        [
            InlineKeyboardButton("Hoy", callback_data=f"date:{today.isoformat()}"),
            InlineKeyboardButton("Mañana", callback_data=f"date:{manana.isoformat()}"),
        ],
        [
            InlineKeyboardButton("Sábado", callback_data=f"date:{proximo_sabado.isoformat()}"),
            InlineKeyboardButton(
                "Próximo Lunes", callback_data=f"date:{proximo_lunes.isoformat()}"
            ),
        ],
        [InlineKeyboardButton("¿Otra fecha?", callback_data="other_date")],
    ]

    return InlineKeyboardMarkup(buttons)


def build_event_selection_keyboard(eventos: list[dict]) -> InlineKeyboardMarkup:
    """Genera botones numerados para seleccionar un evento de la lista.

    Args:
        eventos: Lista de eventos de Google Calendar.

    Returns:
        InlineKeyboardMarkup con botones [1]...[N].
    """
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for i, evento in enumerate(eventos, 1):
        row.append(
            InlineKeyboardButton(
                f"[{i}]",
                callback_data=f"select_event:{i}",
            )
        )
        if len(row) == 5:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


def build_list_submenu_keyboard() -> InlineKeyboardMarkup:
    """Genera el submenú de tipos de listado.

    Returns:
        InlineKeyboardMarkup con 4 opciones de filtro.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 Próximos eventos", callback_data="list:pendientes"),
                InlineKeyboardButton("📆 Por día", callback_data="list:dia"),
            ],
            [
                InlineKeyboardButton("👤 Por cliente", callback_data="list:cliente"),
                InlineKeyboardButton("📜 Historial", callback_data="list:historial"),
            ],
        ]
    )
