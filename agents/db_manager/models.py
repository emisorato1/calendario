"""Dataclasses del dominio de base de datos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Cliente:
    """Representa un cliente en el CRM local."""

    nombre_completo: str
    id_cliente: Optional[int] = None
    alias: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: str = "San Rafael"
    notas_equipamiento: Optional[str] = None
    fecha_alta: Optional[datetime] = None

    def __str__(self) -> str:
        return self.nombre_completo


@dataclass
class Servicio:
    """Representa un registro en el historial de servicios."""

    id_cliente: int
    id_servicio: Optional[int] = None
    calendar_event_id: Optional[str] = None
    fecha_servicio: Optional[datetime] = None
    tipo_trabajo: Optional[str] = None
    descripcion: Optional[str] = None
    estado: str = "pendiente"  # pendiente | realizado | cancelado
