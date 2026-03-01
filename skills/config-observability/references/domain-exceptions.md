# Excepciones de Dominio

## Jerarquía de Excepciones

```python
# src/core/exceptions.py


class AgenteCalendarioError(Exception):
    """Excepción base del sistema."""
    
    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(message)


# ── Errores de Repositorio ──

class DatabaseError(AgenteCalendarioError):
    """Error de base de datos."""
    pass


class ClienteNotFoundError(AgenteCalendarioError):
    """Cliente no encontrado."""
    pass


class EventoNotFoundError(AgenteCalendarioError):
    """Evento no encontrado."""
    pass


class DuplicateClienteError(AgenteCalendarioError):
    """Ya existe un cliente con ese teléfono."""
    pass


# ── Errores de Calendar ──

class CalendarError(AgenteCalendarioError):
    """Error de Google Calendar API."""
    pass


class CalendarSyncError(CalendarError):
    """Error de sincronización BD ↔ Calendar."""
    pass


# ── Errores de LLM ──

class LLMError(AgenteCalendarioError):
    """Error del servicio LLM."""
    pass


class LLMParsingError(LLMError):
    """El LLM devolvió una respuesta no parseable."""
    pass


class LLMUnavailableError(LLMError):
    """Todos los proveedores LLM están caídos."""
    pass


# ── Errores de Negocio ──

class ScheduleConflictError(AgenteCalendarioError):
    """Conflicto de horario: ya hay un evento agendado."""
    pass


class PermissionDeniedError(AgenteCalendarioError):
    """El usuario no tiene permisos para esta acción."""
    pass


class InvalidDateError(AgenteCalendarioError):
    """Fecha u hora inválida (pasada, fuera de rango, etc.)."""
    pass
```

## Manejo Global

```python
# En el orquestador o handler principal
async def safe_execute(coro, update):
    """Ejecuta una corrutina con manejo de errores global."""
    try:
        return await coro
    except PermissionDeniedError:
        await update.message.reply_text("🚫 No tenés permiso para esta acción.")
    except ScheduleConflictError as e:
        await update.message.reply_text(f"⚠️ {e.message}")
    except LLMUnavailableError:
        await update.message.reply_text(
            "⚠️ No pude procesar tu mensaje. Intentá de nuevo o usá /menu."
        )
    except AgenteCalendarioError as e:
        logger.error(f"Error de dominio: {e.message}", exc_info=True)
        await update.message.reply_text("❌ Ocurrió un error. Intentá de nuevo.")
    except Exception as e:
        logger.critical(f"Error inesperado: {e}", exc_info=True)
        await update.message.reply_text("❌ Error inesperado. Contactá al administrador.")
```

## Notas

- Toda excepción del sistema hereda de `AgenteCalendarioError`.
- Los mensajes de error al usuario son amigables, sin detalles técnicos.
- Los detalles técnicos van al log para debugging.
- Usar excepciones específicas (no genéricas) para mayor control.
