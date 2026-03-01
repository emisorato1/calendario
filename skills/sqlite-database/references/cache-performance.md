# Caché y Performance

## Estrategia de Caché

Para reducir consultas a SQLite en operaciones frecuentes (listar clientes,
verificar permisos), se implementa un caché LRU en memoria con TTL.

## Implementación

```python
import time
from typing import Optional, Any
from functools import wraps


class TTLCache:
    """Caché en memoria con Time-To-Live."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 128):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        if len(self._cache) >= self._max_size:
            # Eliminar el más antiguo
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

    def invalidate(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()
```

## Qué Cachear

| Dato                     | TTL        | Razón                                     |
| ------------------------ | ---------- | ----------------------------------------- |
| Lista de clientes        | 5 minutos  | Cambia raramente durante una sesión       |
| Permisos de usuario      | 10 minutos | Casi nunca cambian                         |
| Eventos del día          | 2 minutos  | Pueden cambiar con más frecuencia         |
| Configuración            | 30 minutos | Prácticamente estática                     |

## Invalidación

El caché se invalida automáticamente por TTL. Además, se invalida
manualmente cuando:

- Se crea, edita o elimina un cliente → `cache.invalidate("clientes")`
- Se crea, edita o elimina un evento → `cache.invalidate("eventos_*")`
- Se cambian permisos → `cache.invalidate("permisos_*")`

## Performance SQLite

Además del caché, optimizaciones de SQLite:

```python
# Al inicializar la conexión
PRAGMA journal_mode=WAL;           # Write-Ahead Log
PRAGMA synchronous=NORMAL;         # Balanceado entre seguridad y velocidad
PRAGMA cache_size=-8000;           # 8MB de caché de página
PRAGMA busy_timeout=5000;          # Esperar 5s si la BD está bloqueada
PRAGMA temp_store=MEMORY;          # Tablas temporales en memoria
```
