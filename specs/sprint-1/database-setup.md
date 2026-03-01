# Sprint 1 — Base de Datos y Repositorio

## Descripción

Implementar la capa de persistencia completa: schema SQL, modelos Pydantic,
repository pattern con operaciones CRUD asincrónicas, sistema de migraciones,
búsqueda fuzzy de clientes y caché LRU con TTL.

## Objetivos

- [x] Crear schema SQL con tablas `clientes`, `eventos`, `usuarios_autorizados`.
- [x] Implementar modelos Pydantic para todas las entidades.
- [x] Implementar `Repository` con CRUD asincrónico completo.
- [x] Implementar búsqueda fuzzy de clientes por nombre.
- [x] Implementar caché TTL para consultas frecuentes.
- [x] Crear sistema de migraciones versionado.
- [x] Configurar SQLite con WAL mode y optimizaciones de rendimiento.

## Requisitos Técnicos

| Requisito           | Detalle                                           |
| ------------------- | ------------------------------------------------- |
| SQLite              | v3 con WAL mode                                   |
| Acceso asincrónico  | `aiosqlite`                                       |
| Modelos             | Pydantic v2                                       |
| Fuzzy search        | `thefuzz` con `token_sort_ratio`                  |
| Threshold           | Configurable en `.env` (`FUZZY_MATCH_THRESHOLD`)  |
| Caché               | TTL cache en memoria (custom)                     |

## Pasos de Implementación

### 1. Schema SQL (`src/db/schema.sql`)

- Tabla `clientes`: id, nombre, telefono (UNIQUE), direccion, notas, timestamps.
- Tabla `eventos`: id, cliente_id (FK), google_event_id, tipo_servicio (CHECK),
  fecha_hora, duracion, estado (CHECK), datos de cierre, timestamps.
- Tabla `usuarios_autorizados`: id, telegram_id (UNIQUE), nombre, rol (CHECK),
  activo, timestamp.
- Índices para performance: `estado`, `fecha_hora`, `cliente_id`, `nombre`.
- PRAGMAs de optimización: WAL, foreign_keys, cache_size, busy_timeout.

### 2. Modelos (`src/db/models.py`)

- `TipoServicio` (Enum): instalacion, revision, mantenimiento, reparacion,
  presupuesto, otro, completado.
- `EstadoEvento` (Enum): pendiente, completado, cancelado.
- `Rol` (Enum): admin, editor.
- `Cliente` (BaseModel): con validadores.
- `Evento` (BaseModel): con propiedades derivadas (emoji, hora_formateada).
- `UsuarioAutorizado` (BaseModel).

### 3. Database Manager (`src/db/database.py`)

- `DatabaseManager`: Gestiona conexión, inicialización de schema, y migraciones.
- Métodos: `connect()`, `close()`, `initialize()`, `run_migrations()`.
- Context manager para transacciones.

### 4. Repository (`src/db/repository.py`)

**Clientes:**
- `create_cliente(cliente) → int`
- `get_cliente_by_id(id) → Cliente | None`
- `get_cliente_by_telefono(tel) → Cliente | None`
- `search_clientes_fuzzy(query, threshold) → list[Cliente, score]`
- `list_clientes() → list[Cliente]`
- `update_cliente(id, **kwargs) → bool`

**Eventos:**
- `create_evento(evento) → int`
- `get_evento_by_id(id) → Evento | None`
- `list_eventos_pendientes() → list[Evento]`
- `list_eventos_hoy() → list[Evento]`
- `list_eventos_by_date(date) → list[Evento]`
- `update_evento(id, **kwargs) → bool`
- `complete_evento(id, **closure) → bool`
- `delete_evento(id) → bool`

### 5. Caché (`src/db/cache.py`)

- `TTLCache`: Caché genérica con TTL y max_size.
- Métodos: `get()`, `set()`, `invalidate()`, `clear()`.
- Integración con `Repository`: cachear `list_clientes()` y permisos.

### 6. Tests

- `tests/unit/test_models.py`: Validación de modelos Pydantic.
- `tests/unit/test_repository.py`: CRUD completo con BD en memoria.
- `tests/unit/test_cache.py`: TTL, invalidación, max_size.
- `tests/unit/test_fuzzy.py`: Búsqueda fuzzy con distintos thresholds.

## Criterios de Aceptación

- [x] La BD se crea automáticamente al primer arranque.
- [x] CRUD completo de clientes y eventos funciona.
- [x] Búsqueda fuzzy encuentra "Perez" buscando "Pérez" (score > 75).
- [x] Caché devuelve datos sin consultar la BD cuando son recientes.
- [x] Foreign keys están habilitadas (no se puede crear evento con cliente_id inexistente).
- [x] Todos los tests pasan.

## Skills Referenciadas

- [SQLite Database](../../skills/sqlite-database/SKILL.md)
  - [Schema y Modelos](../../skills/sqlite-database/references/schema-models.md)
  - [Repository Pattern](../../skills/sqlite-database/references/repository-pattern.md)
  - [Búsqueda Fuzzy](../../skills/sqlite-database/references/fuzzy-search.md)
  - [Caché y Performance](../../skills/sqlite-database/references/cache-performance.md)
