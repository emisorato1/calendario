# src/bot/constants.py
"""Constantes del bot: estados de conversación, textos y emojis."""

from src.db.models import TipoServicio


# ── Estados de ConversationHandler ────────────────────────────────────────────
# Cada flujo de conversación define sus propios estados como enteros.


class States:
    """Estados compartidos de ConversationHandler."""

    # Crear evento
    CREAR_DESCRIPTION = 0
    CREAR_DATE = 1
    CREAR_TIME_SLOT = 2
    CREAR_CONFIRMATION = 3

    # Editar evento
    EDITAR_SELECT = 10
    EDITAR_CHANGES = 11
    EDITAR_CONFIRMATION = 12

    # Eliminar evento
    ELIMINAR_SELECT = 20
    ELIMINAR_CONFIRMATION = 21

    # Terminar evento
    TERMINAR_SELECT = 30
    TERMINAR_CLOSURE = 31
    TERMINAR_PHOTOS = 32
    TERMINAR_CONFIRMATION = 33

    # Contactos (editar)
    CONTACTO_SELECT = 40
    CONTACTO_FIELD = 41
    CONTACTO_VALUE = 42
    CONTACTO_CONFIRMATION = 43

    # Timeout (compartido)
    TIMEOUT = -1


# ── Callback Data ─────────────────────────────────────────────────────────────
# Patrones de callback_data para botones inline.


class CallbackData:
    """Prefijos y patrones de callback_data."""

    # Menú principal
    CREAR_EVENTO = "crear_evento"
    EDITAR_EVENTO = "editar_evento"
    VER_EVENTOS = "ver_eventos"
    ELIMINAR_EVENTO = "eliminar_evento"
    TERMINAR_EVENTO = "terminar_evento"
    VER_CONTACTOS = "ver_contactos"
    EDITAR_CONTACTO = "editar_contacto"

    # Confirmación
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"

    # Cancelar
    CANCEL = "cancel"

    # Prefijos de selección
    EVENT_PREFIX = "event_"
    CONTACT_PREFIX = "contact_"
    SLOT_PREFIX = "slot_"
    SLOT_CONFIRM = "slot_confirm"
    FIELD_PREFIX = "field_"

    # Paginación
    NOOP = "noop"

    # Campos editables de contacto
    FIELD_NOMBRE = "field_nombre"
    FIELD_TELEFONO = "field_telefono"
    FIELD_DIRECCION = "field_direccion"
    FIELD_NOTAS = "field_notas"

    # Fotos
    PHOTOS_DONE = "photos_done"
    PHOTOS_SKIP = "photos_skip"


# ── Emojis por Tipo de Servicio ───────────────────────────────────────────────

SERVICE_EMOJIS: dict[TipoServicio, str] = {
    TipoServicio.INSTALACION: "🔵",
    TipoServicio.REVISION: "🟡",
    TipoServicio.MANTENIMIENTO: "🟠",
    TipoServicio.REPARACION: "🟠",
    TipoServicio.PRESUPUESTO: "🟡",
    TipoServicio.OTRO: "⚪",
}


def get_service_emoji(tipo: TipoServicio | str) -> str:
    """Obtiene el emoji correspondiente a un tipo de servicio.

    Args:
        tipo: Tipo de servicio (enum o string).

    Returns:
        Emoji correspondiente o ⚪ por defecto.
    """
    if isinstance(tipo, str):
        try:
            tipo = TipoServicio(tipo)
        except ValueError:
            return "⚪"
    return SERVICE_EMOJIS.get(tipo, "⚪")


# ── Textos de Mensajes ────────────────────────────────────────────────────────


class Messages:
    """Textos centralizados del bot."""

    # Bienvenida
    WELCOME = (
        "👋 ¡Hola {nombre}! Soy el bot de gestión de turnos.\n\n"
        "Usá los botones del menú o escribí en lenguaje natural."
    )

    MENU_HEADER = "📋 *Menú Principal*\n\nElegí una opción:"

    # Crear evento
    DESCRIBE_EVENT = (
        "📝 *Crear Evento*\n\n"
        "Describí el evento en lenguaje natural.\n"
        "Ejemplo: _Mañana a las 10 instalación de cámaras "
        "para Juan Pérez en Balcarce 132_"
    )

    ASK_DATE = "📅 ¿Para qué fecha es el evento?"

    ASK_TIME_SLOT = "🕐 Elegí el horario para el evento:"

    SLOT_MULTI_SELECT = (
        "🕐 Elegí el horario (podés seleccionar hasta 3 bloques consecutivos):"
    )

    DATE_NOT_UNDERSTOOD = (
        "No pude entender la fecha. Por favor indicá un día concreto "
        "(ej: mañana, el viernes, el 15/03)."
    )

    # Editar evento
    SELECT_EVENT_EDIT = "✏️ ¿Cuál evento querés editar?"
    DESCRIBE_CHANGES = (
        "✏️ Describí los cambios que querés hacer.\n"
        "Ejemplo: _Pasalo a las 14_ o _Cambiá el tipo a reparación_"
    )

    # Eliminar evento
    SELECT_EVENT_DELETE = "🗑️ ¿Cuál evento querés eliminar?"
    CONFIRM_DELETE = "⚠️ ¿Estás seguro de que querés eliminar este evento?"

    # Terminar evento
    SELECT_EVENT_COMPLETE = "✅ ¿Cuál evento querés marcar como terminado?"
    DESCRIBE_CLOSURE = (
        "📋 Contame sobre el cierre del servicio.\n"
        "Ejemplo: _Se instalaron 4 cámaras, se cobró $150.000_"
    )
    ASK_PHOTOS = (
        "📸 ¿Querés adjuntar fotos del trabajo realizado?\n"
        "Enviá las fotos o presioná el botón para continuar."
    )

    # Contactos
    NO_CONTACTS = "No hay contactos registrados."
    SELECT_CONTACT = "👥 ¿Cuál contacto querés editar?"
    SELECT_FIELD = "¿Qué campo querés modificar?"
    ASK_NEW_VALUE = "Ingresá el nuevo valor para *{campo}*:"

    # Confirmaciones
    EVENT_CREATED = "✅ Evento creado exitosamente."
    EVENT_UPDATED = "✅ Evento actualizado exitosamente."
    EVENT_DELETED = "✅ Evento eliminado."
    EVENT_COMPLETED = "✅ Evento marcado como completado."
    CONTACT_UPDATED = "✅ Contacto actualizado."
    CREATION_CANCELLED = "Creación de evento cancelada."
    OPERATION_CANCELLED = "Operación cancelada."

    # Errores
    NO_PENDING_EVENTS = "No hay eventos pendientes."
    ERROR_GENERIC = "❌ Error: {error}"
    PERMISSION_DENIED = "🚫 No tenés permiso para esta acción."
    NOT_AUTHORIZED = "🚫 No estás autorizado para usar este bot."
    CONVERSATION_TIMEOUT = (
        "⏰ La conversación expiró por inactividad. Usá /menu para reiniciar."
    )

    # Natural
    UNKNOWN_INTENT = (
        "No entendí tu mensaje. Usá /menu para ver las acciones disponibles."
    )
    GREETING = "¡Hola! ¿En qué puedo ayudarte? Usá /menu para ver las opciones."
    HELP = (
        "Puedo ayudarte con:\n"
        "• Crear, editar o eliminar eventos\n"
        "• Ver tu agenda de eventos pendientes\n"
        "• Gestionar contactos\n"
        "• Marcar eventos como terminados\n\n"
        "Podés escribir en lenguaje natural o usar /menu."
    )


# ── Límite de Telegram ────────────────────────────────────────────────────────

TELEGRAM_MAX_LENGTH = 4096

# ── Paginación ────────────────────────────────────────────────────────────────

ITEMS_PER_PAGE = 5
