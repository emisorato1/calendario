"""Cache LRU en memoria con TTL para búsquedas de clientes frecuentes."""
from __future__ import annotations

import time
from threading import Lock
from typing import Optional

from agents.db_manager.models import Cliente


class ClienteCache:
    """
    Cache en memoria con TTL de 5 minutos para resultados de fuzzy search.

    Thread-safe. Se invalida completamente al crear o actualizar un cliente.
    """

    TTL_SECONDS: int = 300  # 5 minutos

    def __init__(self, ttl_seconds: int = TTL_SECONDS) -> None:
        self._cache: dict[str, tuple[Optional[Cliente], float]] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, key: str) -> Optional[Cliente]:
        """Retorna el cliente cacheado o None si expiró o no existe."""
        with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if time.monotonic() - ts < self._ttl:
                    return value
                # TTL expirado: limpiar la entrada
                del self._cache[key]
        return None

    def set(self, key: str, value: Optional[Cliente]) -> None:
        """Almacena un cliente en caché con timestamp actual."""
        with self._lock:
            self._cache[key] = (value, time.monotonic())

    def invalidate(self, key: str) -> None:
        """Elimina una entrada específica del caché."""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Invalida todo el caché (usar al crear o actualizar clientes)."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)
