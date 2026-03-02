# Schema y Modelos

## SQL de Inicialización

```sql
-- Habilitar WAL mode para mejor concurrencia
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL,
    telefono    TEXT    UNIQUE,
    direccion   TEXT,
    notas       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS eventos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
    google_event_id     TEXT    UNIQUE,
    tipo_servicio       TEXT    NOT NULL CHECK(tipo_servicio IN (
                            'instalacion','revision','mantenimiento',
                            'reparacion','presupuesto','otro'
                        )),
    prioridad           TEXT    NOT NULL DEFAULT 'normal' CHECK(prioridad IN (
                            'normal','alta'
                        )),
    fecha_hora          TEXT    NOT NULL,
    duracion_minutos    INTEGER NOT NULL DEFAULT 60,
    estado              TEXT    NOT NULL DEFAULT 'pendiente' CHECK(estado IN (
                            'pendiente','completado','cancelado'
                        )),
    notas               TEXT,
    trabajo_realizado   TEXT,
    monto_cobrado       REAL,
    notas_cierre        TEXT,
    fotos               TEXT,  -- JSON array de rutas
    created_at          TEXT   NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at          TEXT   NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS usuarios_autorizados (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id  INTEGER UNIQUE NOT NULL,
    nombre       TEXT,
    rol          TEXT    NOT NULL CHECK(rol IN ('admin','editor')),
    activo       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos(estado);
CREATE INDEX IF NOT EXISTS idx_eventos_fecha ON eventos(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_eventos_cliente ON eventos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre);
```

## Modelos Pydantic

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
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


class EstadoEvento(str, Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class Rol(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"


class Cliente(BaseModel):
    id: Optional[int] = None
    nombre: str = Field(min_length=1)  # No permite nombres vacíos
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Evento(BaseModel):
    id: Optional[int] = None
    cliente_id: int
    google_event_id: Optional[str] = None
    tipo_servicio: TipoServicio
    prioridad: Prioridad = Prioridad.NORMAL
    fecha_hora: datetime
    duracion_minutos: int = Field(default=60, ge=15, le=480)
    estado: EstadoEvento = EstadoEvento.PENDIENTE
    notas: Optional[str] = None
    trabajo_realizado: Optional[str] = None
    monto_cobrado: Optional[float] = Field(default=None, ge=0)  # No permite montos negativos
    notas_cierre: Optional[str] = None
    fotos: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

## Notas

- Los timestamps se almacenan como ISO 8601 strings en SQLite.
- `fotos` se serializa como JSON array de strings.
- Foreign keys están habilitadas explícitamente con `PRAGMA foreign_keys=ON`.
- Los índices cubren las consultas más frecuentes (listar pendientes, buscar por fecha).
- `Cliente.nombre` requiere `min_length=1` — no se permiten nombres vacíos.
- `Evento.monto_cobrado` requiere `ge=0` — no se permiten montos negativos.
- Los campos de horario laboral en `Settings` (`work_days_*`) se validan con formato `HH:MM` y rango `00:00-23:59`.
- `TipoServicio` NO incluye "completado" — el estado de completitud se maneja
  exclusivamente con `EstadoEvento.COMPLETADO`. Esto evita la ambigüedad entre
  un *tipo de servicio* y un *estado del evento*.
