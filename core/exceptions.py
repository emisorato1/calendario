"""Jerarquía de excepciones personalizadas del Agente Calendario."""


# ── Base ──────────────────────────────────────────────────────────────────────

class AgenteCalendarioError(Exception):
    """Excepción base del proyecto. Todas las demás heredan de esta."""


# ── DB ────────────────────────────────────────────────────────────────────────

class DBError(AgenteCalendarioError):
    """Error genérico de base de datos."""


class ClienteNoEncontradoError(DBError):
    """El cliente buscado no existe en la base de datos."""


class DBMigrationError(DBError):
    """Error durante la ejecución de migraciones."""


# ── Groq Parser ───────────────────────────────────────────────────────────────

class GroqError(AgenteCalendarioError):
    """Error genérico de la API de Groq."""


class GroqParsingError(GroqError):
    """El LLM retornó una respuesta que no se pudo parsear como JSON."""


class GroqTimeoutError(GroqError):
    """La llamada a Groq superó el tiempo de espera."""


# ── Calendar ──────────────────────────────────────────────────────────────────

class CalendarError(AgenteCalendarioError):
    """Error genérico de Google Calendar."""


class EventoNoEncontradoError(CalendarError):
    """El evento buscado no existe en el calendario."""


class ConflictoHorarioError(CalendarError):
    """El horario solicitado tiene conflicto con un evento existente."""


class CalendarAuthError(CalendarError):
    """Error de autenticación con la API de Google Calendar."""


# ── Telegram ──────────────────────────────────────────────────────────────────

class TelegramError(AgenteCalendarioError):
    """Error genérico de Telegram."""


class AccesoNoAutorizadoError(TelegramError):
    """El usuario que envió el mensaje no está autorizado."""
