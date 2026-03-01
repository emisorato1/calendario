"""Constantes del dominio. Sin dependencias externas."""

# ── Duraciones por tipo de servicio (en horas) ────────────────────────────────
DURACIONES_SERVICIO: dict[str, float] = {
    "instalacion": 3.0,
    "revision": 1.0,
    "mantenimiento": 2.0,
    "presupuesto": 1.0,
    "reparacion": 2.0,
    "otro": 1.0,
}

# ── Colores de Google Calendar (ID de color) ──────────────────────────────────
COLOR_MAP: dict[str, str] = {
    "reparacion":    "6",   # Mandarina/Naranja
    "mantenimiento": "6",   # Mandarina/Naranja
    "instalacion":   "9",   # Arándano/Azul
    "revision":      "5",   # Plátano/Amarillo
    "presupuesto":   "5",   # Plátano/Amarillo
    "otro":          "8",   # Grafito
}

COLOR_EMOJI: dict[str, str] = {
    "6": "🟠",
    "9": "🔵",
    "5": "🟡",
    "8": "⚫",
}

# ── Zona horaria ──────────────────────────────────────────────────────────────
TIMEZONE = "America/Argentina/Buenos_Aires"

# ── Horario laboral (valores por defecto, overrideables desde .env) ───────────
# weekday() de Python: 0=Lunes, 1=Martes, ..., 5=Sábado, 6=Domingo
WORK_SCHEDULE: dict[str, dict | None] = {
    "weekday": {        # Lunes (0) a Viernes (4)
        "start": "15:00",
        "end": "21:00",
        "total_hours": 6.0,
    },
    "saturday": {       # Sábado (5)
        "start": "08:00",
        "end": "20:00",
        "total_hours": 12.0,
    },
    "sunday": None,     # Sin actividad
}

# Días laborales: conjunto de weekday() de Python
WORK_DAYS: set[int] = {0, 1, 2, 3, 4, 5}   # Lunes a Sábado

# Intervalo de tiempo entre franjas para los botones de sugerencia
TIME_SLOT_INTERVAL_MINUTES: int = 60

# ── Estados SQLite de servicios ───────────────────────────────────────────────
ESTADO_PENDIENTE = "pendiente"
ESTADO_REALIZADO = "realizado"
ESTADO_CANCELADO = "cancelado"
ESTADOS_VALIDOS: set[str] = {ESTADO_PENDIENTE, ESTADO_REALIZADO, ESTADO_CANCELADO}
