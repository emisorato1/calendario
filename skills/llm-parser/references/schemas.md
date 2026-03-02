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


class Prioridad(str, Enum):
    NORMAL = "normal"
    ALTA = "alta"


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
    tipo_servicio: TipoServicio = Field(default=TipoServicio.OTRO)
    fecha: Optional[date] = None
    hora: Optional[time] = None
    duracion_minutos: int = Field(default=60, ge=15, le=480)
    notas: Optional[str] = None
    prioridad: Prioridad = Field(default=Prioridad.NORMAL)
    missing_fields: list[str] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("tipo_servicio", mode="before")
    @classmethod
    def tipo_never_null(cls, v):
        """Garantiza que tipo_servicio NUNCA sea null. Default: 'otro'."""
        if v is None:
            return TipoServicio.OTRO
        return v

    @property
    def needs_clarification(self) -> bool:
        return len(self.missing_fields) > 0 or self.confidence < 0.6

    @property
    def is_complete(self) -> bool:
        required = [self.cliente_nombre, self.fecha, self.hora]
        return all(f is not None for f in required) and not self.needs_clarification

    @property
    def has_date_but_no_time(self) -> bool:
        """True si tiene fecha pero falta la hora (para mostrar botones de horarios)."""
        return self.fecha is not None and self.hora is None

    @property
    def is_high_priority(self) -> bool:
        """True si es prioridad alta (permite bypass de superposición)."""
        return self.prioridad == Prioridad.ALTA


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
- `confidence < 0.6` activa la pregunta de clarificación. Default `1.0`
  para que datos construidos programáticamente no disparen clarificación falsa;
  el LLM devolverá un valor bajo cuando esté inseguro.
- `tipo_servicio` NUNCA puede ser null — el validador lo fuerza a `"otro"`.
- `prioridad="alta"` permite al Orquestador crear eventos con superposición.
- `has_date_but_no_time` se usa para activar el flujo de botones de horarios
  disponibles (el handler no pregunta por texto, muestra inline buttons).
- `is_complete` ya no requiere `tipo_servicio` en la lista de required porque
  siempre tiene valor (default `"otro"`).
