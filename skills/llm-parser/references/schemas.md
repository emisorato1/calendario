# Schemas Pydantic

## Propósito

Definir schemas estrictos para validar la salida del LLM. Toda respuesta del
LLM se parsea y valida contra estos modelos antes de ser utilizada.

## Schemas Principales

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, time
from enum import Enum


class TipoServicio(str, Enum):
    INSTALACION = "instalacion"
    REVISION = "revision"
    MANTENIMIENTO = "mantenimiento"
    REPARACION = "reparacion"
    PRESUPUESTO = "presupuesto"
    OTRO = "otro"


class Intent(str, Enum):
    CREAR_EVENTO = "crear_evento"
    EDITAR_EVENTO = "editar_evento"
    VER_EVENTOS = "ver_eventos"
    ELIMINAR_EVENTO = "eliminar_evento"
    TERMINAR_EVENTO = "terminar_evento"
    VER_CONTACTOS = "ver_contactos"
    EDITAR_CONTACTO = "editar_contacto"
    SALUDO = "saludo"
    AYUDA = "ayuda"
    DESCONOCIDO = "desconocido"


class ParsedEvent(BaseModel):
    """Resultado del parsing de un evento nuevo."""
    intent: Intent = Intent.CREAR_EVENTO
    cliente_nombre: Optional[str] = None
    cliente_telefono: Optional[str] = None
    direccion: Optional[str] = None
    tipo_servicio: Optional[TipoServicio] = None
    fecha: Optional[date] = None
    hora: Optional[time] = None
    duracion_minutos: int = Field(default=60, ge=15, le=480)
    notas: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def needs_clarification(self) -> bool:
        return len(self.missing_fields) > 0 or self.confidence < 0.6

    @property
    def is_complete(self) -> bool:
        required = [self.cliente_nombre, self.tipo_servicio, self.fecha, self.hora]
        return all(f is not None for f in required) and not self.needs_clarification


class ParsedEdit(BaseModel):
    """Resultado del parsing de una edición."""
    intent: Intent = Intent.EDITAR_EVENTO
    changes: dict[str, str] = Field(default_factory=dict)
    clarification_question: Optional[str] = None


class ParsedClosure(BaseModel):
    """Resultado del parsing de un cierre de servicio."""
    intent: Intent = Intent.TERMINAR_EVENTO
    trabajo_realizado: Optional[str] = None
    monto_cobrado: Optional[float] = Field(default=None, ge=0)
    notas_cierre: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    clarification_question: Optional[str] = None


class IntentDetection(BaseModel):
    """Resultado de la detección de intención general."""
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_data: dict = Field(default_factory=dict)
```

## Validación de Respuesta del LLM

```python
import json
from pydantic import ValidationError

def parse_llm_response(raw_json: str, schema_class: type[BaseModel]) -> BaseModel:
    """
    Parsea y valida la respuesta JSON del LLM.
    
    Raises:
        ValueError: Si el JSON es inválido o no cumple el schema.
    """
    try:
        data = json.loads(raw_json)
        return schema_class.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Respuesta del LLM inválida: {e}")
```

## Notas

- Siempre validar antes de usar los datos.
- Si la validación falla, se reintenta con el LLM (máximo 2 veces).
- Los valores por defecto permiten parsing parcial.
- `confidence < 0.6` activa la pregunta de clarificación.
