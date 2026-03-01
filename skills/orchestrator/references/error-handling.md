# Manejo de Errores y Result Pattern

## Principio

Nunca lanzar excepciones no controladas al usuario. Toda operación del
orquestador devuelve un objeto `Result` tipado que indica éxito, error
o necesidad de interacción adicional.

## Result Pattern

```python
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class ResultStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    NEEDS_INPUT = "needs_input"
    CONFLICT = "conflict"


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
    await update.message.reply_text(result.question)
    return WAITING_DESCRIPTION  # Volver a pedir datos
elif result.status == ResultStatus.CONFLICT:
    await update.message.reply_text(f"⚠️ {result.message}")
else:
    await update.message.reply_text(f"❌ Error: {result.message}")
    logger.error(f"Error en crear evento: {result.errors}")
```

## Errores Comunes y Mensajes

| Error Técnico                  | Mensaje al Usuario                              |
| ------------------------------ | ------------------------------------------------ |
| LLM timeout                   | "No pude procesar tu mensaje. Intentá de nuevo." |
| Calendar API error             | "Hubo un problema con el calendario. Reintentá."  |
| DB constraint violation        | "Ya existe un cliente con ese teléfono."          |
| Fecha pasada                   | "La fecha indicada ya pasó. Elegí otra."          |
| Sin permisos                   | "No tenés permiso para esta acción."              |
| Datos insuficientes            | "Necesito más información: {campos_faltantes}"   |

## Notas

- Los errores técnicos se loguean con detalle; al usuario solo se muestra
  un mensaje amigable.
- El `Result` permite que el handler tome decisiones sin conocer la
  implementación interna del orquestador.
