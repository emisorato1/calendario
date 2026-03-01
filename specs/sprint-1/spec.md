# Sprint 1 — Fundamentos (Config + DB + Infraestructura)

> **Duración estimada**: 3-4 sesiones de trabajo  
> **Objetivo**: Tener la base del proyecto funcionando — configuración, logging, base de datos y tests.  
> **Pre-requisito**: Ninguno — es el punto de entrada del proyecto.

---

## Entregables

### 1. Estructura de Carpetas

```
agente-calendario-v2/
├── agents/
│   ├── __init__.py
│   ├── telegram_listener/
│   │   └── __init__.py
│   ├── groq_parser/
│   │   └── __init__.py
│   ├── db_manager/
│   │   └── __init__.py
│   └── calendar_sync/
│       └── __init__.py
├── core/
│   └── __init__.py
├── config/
│   └── __init__.py
├── data/
│   └── backups/
├── logs/
├── credentials/
├── scripts/
├── tests/
│   └── __init__.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── requirements.txt
```

### 2. `config/settings.py`

- `Settings` con `pydantic-settings` (lee desde `.env`).
- Campos requeridos (fail-fast si faltan):
  - `TELEGRAM_BOT_TOKEN: str`
  - `ADMIN_TELEGRAM_IDS: list[int]` — IDs de cuentas Admin separados por coma en `.env` (ej: `123,456`). Mínimo 1, máximo 2.
  - `GROQ_API_KEY: str`
  - `GOOGLE_CALENDAR_ID: str`
  - `GOOGLE_SERVICE_ACCOUNT_PATH: str`
- Campos opcionales con defaults:
  - `EDITOR_TELEGRAM_IDS: list[int] = []` — IDs de cuentas Editor. Puede estar vacío.
  - `SQLITE_DB_PATH: str = "data/agenda.db"`
  - `LOG_LEVEL: str = "INFO"`
  - `GROQ_MODEL_PRIMARY: str = "llama-3.3-70b-versatile"`
  - `GROQ_MODEL_FALLBACK: str = "llama-3.1-8b-instant"`
  - `CONFLICT_BUFFER_MINUTES: int = 30`
  - `MAX_EVENTS_LIST: int = 10`
  - `WORK_DAYS_WEEKDAY_START: time = time(15, 0)` — Inicio jornada lunes a viernes.
  - `WORK_DAYS_WEEKDAY_END: time = time(21, 0)` — Fin jornada lunes a viernes.
  - `WORK_DAYS_SATURDAY_START: time = time(8, 0)` — Inicio jornada sábados.
  - `WORK_DAYS_SATURDAY_END: time = time(20, 0)` — Fin jornada sábados.
- **Validadores de modelo**:
  - `ADMIN_TELEGRAM_IDS` no puede tener más de 2 elementos → `ValueError`.
  - No puede haber IDs duplicados entre `ADMIN_TELEGRAM_IDS` y `EDITOR_TELEGRAM_IDS` → `ValueError`.
  - Métodos de conveniencia:
    ```python
    def is_admin(self, user_id: int) -> bool: ...
    def is_editor(self, user_id: int) -> bool: ...
    def is_authorized(self, user_id: int) -> bool: ...
    ```

### 3. `config/constants.py`

```python
# Duraciones por tipos de servicio (en horas)
DURACIONES_SERVICIO = {
    "instalacion": 3.0,
    "revision": 1.0,
    "mantenimiento": 2.0,
    "presupuesto": 1.0,
    "reparacion": 2.0,
    "otro": 1.0,
}

# Colores de Google Calendar
COLOR_MAP = {
    "reparacion":    "6",   # Mandarina/Naranja
    "mantenimiento": "6",  # Mandarina/Naranja
    "instalacion":   "9",  # Arándano/Azul
    "revision":      "5",  # Plátano/Amarillo
    "presupuesto":   "5",  # Plátano/Amarillo
    "otro":          "8",  # Grafito
}

TIMEZONE = "America/Argentina/Buenos_Aires"

# Horario laboral por tipo de día (línea base, overrideable en .env)
# weekday() en Python: 0=Lunes, 1=Martes, ..., 5=Sábado, 6=Domingo
WORK_SCHEDULE = {
    "weekday": {  # Lunes (0) a Viernes (4)
        "start": "15:00",
        "end": "21:00",
        "total_hours": 6.0,
    },
    "saturday": {  # Sábado (5)
        "start": "08:00",
        "end": "20:00",
        "total_hours": 12.0,
    },
    "sunday": None,  # Sin actividad
}

# Días laborales (weekday() de Python)
WORK_DAYS = {0, 1, 2, 3, 4, 5}  # Lunes a Sábado

# Franjas horarias comunes para botones de sugerencia
# (se generan dinámicamente a partir de WORK_SCHEDULE en runtime)
TIME_SLOT_INTERVAL_MINUTES = 60  # Botones de 1 hora por defecto
```

### 4. `core/logger.py`

- Configuración de `structlog` con formato JSON.
- Rotación de archivo de log (`logs/agente.log`, max 10MB, 5 backups).
- Formato: `timestamp ISO | level | módulo | mensaje | contexto`.

### 5. `core/exceptions.py`

Jerarquía de excepciones personalizadas:

```python
class AgenteCalendarioError(Exception): ...

# DB
class DBError(AgenteCalendarioError): ...
class ClienteNoEncontradoError(DBError): ...
class DBMigrationError(DBError): ...

# Groq Parser
class GroqError(AgenteCalendarioError): ...
class GroqParsingError(GroqError): ...
class GroqTimeoutError(GroqError): ...

# Calendar
class CalendarError(AgenteCalendarioError): ...
class EventoNoEncontradoError(CalendarError): ...
class ConflictoHorarioError(CalendarError): ...
class CalendarAuthError(CalendarError): ...

# Telegram
class TelegramError(AgenteCalendarioError): ...
class AccesoNoAutorizadoError(TelegramError): ...
```

### 6. `agents/db_manager/` — COMPLETO

#### `connection.py`
- Context manager async con `aiosqlite`.
- Activa WAL mode y FOREIGN KEYS en cada conexión.
- Timeout configurable.

#### `models.py`
- `Cliente` (dataclass): `id_cliente`, `nombre_completo`, `alias`, `telefono`, `direccion`, `ciudad`, `notas_equipamiento`, `fecha_alta`.
- `Servicio` (dataclass): `id_servicio`, `id_cliente`, `calendar_event_id`, `fecha_servicio`, `tipo_trabajo`, `descripcion`, `estado`.

#### `migrations.py`
- Crea tablas `clientes` e `historial_servicios` con índices.
- Gestiona `schema_version` para idempotencia.
- Se puede ejecutar N veces sin error ni duplicados.

**Schema SQL completo:**
```sql
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    alias TEXT,
    telefono TEXT,
    direccion TEXT,
    ciudad TEXT DEFAULT 'San Rafael',
    notas_equipamiento TEXT,
    fecha_alta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre_completo);

CREATE TABLE IF NOT EXISTS historial_servicios (
    id_servicio INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    calendar_event_id TEXT,
    fecha_servicio DATETIME,
    tipo_trabajo TEXT,
    descripcion TEXT,
    estado TEXT DEFAULT 'pendiente',
    FOREIGN KEY(id_cliente) REFERENCES clientes(id_cliente)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    aplicada_en DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `repository.py`
- `buscar_cliente_fuzzy(nombre: str, threshold: int = 75) -> Cliente | None` — Usa `thefuzz` para tolerancia de errores.
- `crear_cliente(datos: dict) -> Cliente` — INSERT + retorna el objeto creado.
- `actualizar_cliente(id_cliente: int, cambios: dict) -> Cliente` — UPDATE parcial.
- `registrar_servicio(servicio: Servicio) -> int` — INSERT en historial, retorna ID.
- `actualizar_estado_servicio(id_servicio: int, estado: str) -> None` — Para marcar cancelados.
- `listar_clientes(limit: int = 10) -> list[Cliente]` — Últimos clientes con actividad.

#### `cache.py`
- LRU cache en memoria para nombres de clientes frecuentes.
- TTL de 5 minutos.
- Invalidar caché al crear/actualizar clientes.

### 7. Tests

#### `tests/conftest.py`
- Fixture `db_connection` — SQLite `:memory:` con migraciones aplicadas.
- Fixture `mock_settings` — Settings con valores de test, sin `.env`.

#### `tests/test_config_and_core.py`
- Settings falla si falta variable requerida.
- Settings carga defaults correctamente.
- Logger escribe en formato estructurado.
- Excepciones heredan de `AgenteCalendarioError`.

#### `tests/test_db_manager/`
- `test_migrations.py`: Idempotencia de migraciones.
- `test_repository.py`: CRUD completo + fuzzy search.
- `test_connection.py`: WAL mode, foreign keys activos.

---

## Criterios de Aceptación

- [ ] `pytest tests/test_config_and_core.py tests/test_db_manager/` pasa al 100%.
- [ ] `Settings` lanza `ValidationError` si falta `TELEGRAM_BOT_TOKEN` o `GROQ_API_KEY`.
- [ ] `Settings` lanza `ValidationError` si `ADMIN_TELEGRAM_IDS` tiene más de 2 IDs.
- [ ] `Settings` lanza `ValidationError` si hay IDs duplicados entre Admin y Editor.
- [ ] `is_admin()`, `is_editor()`, `is_authorized()` funcionan correctamente.
- [ ] Fuzzy search encuentra "Garcia" buscando "Garzia" con score ≥ 75%.
- [ ] Migraciones son idempotentes (N ejecuciones, 0 errores).
- [ ] Logs se escriben en formato estructurado JSON.
- [ ] El proyecto se puede clonar, instalar venv y correr `pytest` sin `.env`.

---

## Dependencias (`requirements.txt` parcial)

```
aiosqlite>=0.19.0
thefuzz[speedup]>=0.22.0
pydantic>=2.0
pydantic-settings>=2.0
structlog>=24.0
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
```
