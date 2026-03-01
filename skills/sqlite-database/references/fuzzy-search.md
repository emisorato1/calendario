# Búsqueda Fuzzy de Clientes

## Propósito

Cuando el usuario menciona un nombre de cliente en lenguaje natural, puede
que no coincida exactamente con lo que está en la BD. La búsqueda fuzzy
permite encontrar coincidencias aproximadas.

## Implementación

```python
from thefuzz import fuzz, process
from src.db.models import Cliente


def fuzzy_search_cliente(
    query: str,
    clientes: list[Cliente],
    threshold: int = 75,
    limit: int = 5,
) -> list[tuple[Cliente, int]]:
    """
    Busca clientes por nombre con coincidencia aproximada.
    
    Args:
        query: Nombre a buscar.
        clientes: Lista de clientes en la BD.
        threshold: Puntaje mínimo de coincidencia (0-100).
        limit: Máximo de resultados a devolver.
    
    Returns:
        Lista de (Cliente, score) ordenada por score desc.
    """
    if not clientes:
        return []

    choices = {c.id: c.nombre for c in clientes}
    results = process.extract(
        query,
        choices,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
    )

    matched = []
    clientes_by_id = {c.id: c for c in clientes}
    for nombre, score, client_id in results:
        if score >= threshold:
            matched.append((clientes_by_id[client_id], score))

    return matched
```

## Configuración

- **`FUZZY_MATCH_THRESHOLD`**: Configurable en `.env` (default: 75).
- Valores más altos = más estricto, menos falsos positivos.
- Valores más bajos = más permisivo, más resultados pero posibles errores.

## Escenarios

| Nombre en BD    | Búsqueda del usuario | Score | ¿Match? (th=75) |
| --------------- | -------------------- | ----- | ---------------- |
| Juan Pérez      | "Juan Perez"         | 95    | ✅                |
| Juan Pérez      | "Juan"               | 67    | ❌                |
| María García    | "Garcia Maria"       | 90    | ✅                |
| Pedro Martínez  | "Martinez Pedro"     | 90    | ✅                |
| Pedro Martínez  | "Martin"             | 60    | ❌                |

## Notas

- `token_sort_ratio` es ideal para nombres porque ignora el orden de las palabras.
- La búsqueda se hace en memoria sobre la lista cacheada de clientes.
- Si hay una coincidencia perfecta (score = 100), usarla directamente sin preguntar.
- Si hay múltiples matches con score similar, preguntar al usuario cuál es.
