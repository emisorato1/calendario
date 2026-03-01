"""Schemas Pydantic para el Motor NLU (Groq Parser)."""
from __future__ import annotations

import re
from datetime import date, time
from enum import Enum

from pydantic import BaseModel, field_validator, model_validator

from config.constants import DURACIONES_SERVICIO


# ── Enums ─────────────────────────────────────────────────────────────────────


class Intencion(str, Enum):
    agendar = "agendar"
    cancelar = "cancelar"
    editar = "editar"
    listar_pendientes = "listar_pendientes"
    listar_historial = "listar_historial"
    listar_dia = "listar_dia"
    listar_cliente = "listar_cliente"
    otro = "otro"


class TipoServicio(str, Enum):
    instalacion = "instalacion"
    revision = "revision"
    mantenimiento = "mantenimiento"
    presupuesto = "presupuesto"
    reparacion = "reparacion"
    otro = "otro"


# ── ParsedMessage ─────────────────────────────────────────────────────────────


class ParsedMessage(BaseModel):
    """Resultado de parsear un mensaje de texto natural con el LLM."""

    intencion: Intencion
    nombre_cliente: str | None = None
    tipo_servicio: TipoServicio | None = None
    fecha: date | None = None
    hora: time | None = None
    duracion_estimada_horas: float | None = None
    direccion: str | None = None
    telefono: str | None = None
    fecha_consulta: date | None = None
    cliente_consulta: str | None = None
    urgente: bool = False

    # ── Validadores de campo ─────────────────────────────────────────────

    @field_validator("telefono", mode="before")
    @classmethod
    def validar_telefono(cls, v: str | None) -> str | None:
        """Solo dígitos, 8-13 caracteres."""
        if v is None:
            return v
        digitos = re.sub(r"\D", "", str(v))
        if not (8 <= len(digitos) <= 13):
            raise ValueError(
                f"Teléfono debe tener entre 8 y 13 dígitos, recibido: {len(digitos)}"
            )
        return digitos

    # ── Validadores de modelo ────────────────────────────────────────────

    @model_validator(mode="after")
    def validar_fecha_no_pasada(self) -> "ParsedMessage":
        """La fecha no puede ser anterior a hoy."""
        if self.fecha is not None and self.fecha < date.today():
            raise ValueError(
                f"La fecha {self.fecha} es anterior a hoy ({date.today()})"
            )
        return self

    @model_validator(mode="after")
    def inferir_duracion(self) -> "ParsedMessage":
        """Infiere duracion_estimada_horas del tipo_servicio si no viene explícita."""
        if self.duracion_estimada_horas is None and self.tipo_servicio is not None:
            self.duracion_estimada_horas = DURACIONES_SERVICIO.get(
                self.tipo_servicio.value, 1.0
            )
        return self


# ── EditInstruction ──────────────────────────────────────────────────────────


class EditInstruction(BaseModel):
    """Instrucción de edición: al menos un campo debe tener valor."""

    nueva_fecha: date | None = None
    nueva_hora: time | None = None
    nuevo_tipo_servicio: TipoServicio | None = None
    nueva_direccion: str | None = None
    nuevo_telefono: str | None = None
    nueva_duracion_horas: float | None = None

    @model_validator(mode="after")
    def al_menos_un_campo(self) -> "EditInstruction":
        """Al menos un campo debe ser no-None."""
        campos = [
            self.nueva_fecha,
            self.nueva_hora,
            self.nuevo_tipo_servicio,
            self.nueva_direccion,
            self.nuevo_telefono,
            self.nueva_duracion_horas,
        ]
        if all(c is None for c in campos):
            raise ValueError(
                "EditInstruction debe tener al menos un campo con valor"
            )
        return self
