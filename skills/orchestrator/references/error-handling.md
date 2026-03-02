# Manejo de Errores y Result Pattern

## Principio

Nunca lanzar excepciones no controladas al usuario. Toda operación del
orquestador devuelve un objeto `Result` tipado que indica éxito, error
o necesidad de interacción adicional.

## Result Pattern

```python
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import time
from enum import Enum


class ResultStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    NEEDS_INPUT = "needs_input"
    CONFLICT = "conflict"


@dataclass
class AvailableSlot:
    """Un bloque horario disponible."""
    start: time
    end: time

    def __str__(self):
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


@dataclass
class Result:
    """Resultado genérico de una operación del orquestador."""
    status: ResultStatus
    data: Optional[Any] = None
    message: Optional[str] = None
    question: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == ResultStatus.SUCCESS

    @property
    def needs_input(self) -> bool:
        return self.status == ResultStatus.NEEDS_INPUT

    @staticmethod
    def success(data=None, message=None):
        return Result(status=ResultStatus.SUCCESS, data=data, message=message)

    @staticmethod
    def error(message: str, errors: list[str] = None):
        return Result(status=ResultStatus.ERROR, message=message, errors=errors or [])

    @staticmethod
    def needs_clarification(question: str):
        return Result(status=ResultStatus.NEEDS_INPUT, question=question)

    @staticmethod
    def conflict(message: str):
        return Result(status=ResultStatus.CONFLICT, message=message)
```

## Uso en Handlers

```python
# En el handler de Telegram
result = await orchestrator.create_event_from_text(text, user_id)

if result.ok:
    await update.message.reply_text(
        format_event_confirmation(result.data)
    )
elif result.needs_input:
    # Puede ser: falta fecha, falta hora (con slots), o faltan otros datos
    if result.data and result.data.get("available_slots"):
        # Mostrar botones de horarios disponibles
        keyboard = build_time_slots_keyboard(result.data["available_slots"])
        await update.message.reply_text(
            result.question, reply_markup=keyboard
        )
        return WAITING_TIME_SLOT
    else:
        await update.message.reply_text(result.question)
        return WAITING_DESCRIPTION
elif result.status == ResultStatus.CONFLICT:
    # Superposición de horario
    if result.data and result.data.get("available_slots"):
        # Hay horarios alternativos → mostrar botones
        keyboard = build_time_slots_keyboard(result.data["available_slots"])
        await update.message.reply_text(
            f"⚠️ {result.message}", reply_markup=keyboard
        )
        return WAITING_TIME_SLOT
    else:
        # No quedan horarios → pedir otro día
        await update.message.reply_text(
            f"⚠️ {result.message}\n"
            f"No quedan horarios disponibles para ese día. "
            f"¿Querés elegir otro día?"
        )
        return WAITING_DATE
else:
    await update.message.reply_text(f"❌ Error: {result.message}")
    logger.error(f"Error en crear evento: {result.errors}")
```

## Errores Comunes y Mensajes

| Error Técnico                  | Mensaje al Usuario                                          |
| ------------------------------ | ----------------------------------------------------------- |
| LLM timeout                   | "No pude procesar tu mensaje. Intentá de nuevo."            |
| Calendar API error             | "Hubo un problema con el calendario. Reintentá."            |
| DB constraint violation        | "Ya existe un cliente con ese teléfono."                    |
| Fecha pasada                   | "La fecha indicada ya pasó. Elegí otra."                    |
| Sin permisos                   | "No tenés permiso para esta acción."                        |
| Datos insuficientes            | "Necesito más información: {campos_faltantes}"              |
| Falta fecha (no asume hoy)    | "¿Para qué fecha es el evento?"                             |
| Falta hora                    | (Sin texto, muestra botones de horarios disponibles)         |
| Superposición con alternativas | "Ya hay un evento a esa hora. Horarios disponibles: [btns]" |
| Superposición sin alternativas | "No quedan horarios para ese día. ¿Querés elegir otro día?" |
| Prioridad alta + superposición| (Se crea el evento sin mostrar error de conflicto)           |

## Notas

- Los errores técnicos se loguean con detalle; al usuario solo se muestra
  un mensaje amigable.
- El `Result` permite que el handler tome decisiones sin conocer la
  implementación interna del orquestador.
