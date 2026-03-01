# 🗄️ SQLite Database — Persistencia y CRM

Módulo encargado de la persistencia de datos: clientes, eventos y usuarios
autorizados. Implementa un CRM liviano usando SQLite como base de datos
embebida.

## Propósito

Mantener un registro centralizado y confiable de todos los clientes, eventos
y usuarios del sistema. SQLite se elige por su simplicidad, portabilidad y
mínimo uso de recursos (ideal para Ubuntu Server con hardware limitado).

## Casos de Uso

- **CRUD de clientes**: Crear, leer, actualizar y buscar clientes.
- **CRUD de eventos**: Crear, leer, actualizar, eliminar y listar eventos.
- **Búsqueda fuzzy**: Encontrar clientes por nombre aproximado.
- **Caché LRU**: Cachear clientes frecuentes para reducir consultas.
- **Migraciones**: Versionado de schema para actualizaciones seguras.
- **Sincronización**: Mantener la BD como fuente de verdad, sincronizada
  con Google Calendar.

## Tecnología

- **SQLite 3** con WAL mode (better concurrency).
- **`aiosqlite`** para acceso asincrónico.
- **Pydantic v2** para modelos de datos.
- **`thefuzz`** para búsqueda fuzzy de nombres.
- **`functools.lru_cache`** / caché custom con TTL para contactos.

## Patrones

- **Repository Pattern**: Separar lógica de acceso a datos del resto.
- **Unit of Work**: Transacciones atómicas para operaciones multi-tabla.
- **Migration System**: Schema versionado con scripts SQL numerados.
- **WAL Mode**: Habilitado al inicializar para mejor rendimiento concurrente.

## Anti-patrones a Evitar

- ❌ SQL queries directas en handlers o lógica de negocio.
- ❌ Strings concatenados para construir queries (SQL injection).
- ❌ Olvidar cerrar conexiones o no usar context managers.
- ❌ Almacenar timestamps sin timezone.
- ❌ No manejar errores de constraint (UNIQUE, FK, NOT NULL).

## Referencias

- [Schema y Modelos](references/schema-models.md)
- [Repository Pattern](references/repository-pattern.md)
- [Búsqueda Fuzzy](references/fuzzy-search.md)
- [Caché y Performance](references/cache-performance.md)
