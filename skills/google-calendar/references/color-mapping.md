# Colores y Mapping

## Mapa de Colores Google Calendar

Google Calendar usa IDs numéricos para los colores de eventos:

| Color ID | Color Visual      | Tipo de Servicio Asignado       |
| -------- | ----------------- | ------------------------------- |
| `1`      | Lavender          | —                               |
| `2`      | Sage (Verde)      | ✅ **Evento Completado** (vía `EstadoEvento`, no `TipoServicio`) |
| `3`      | Grape             | —                               |
| `4`      | Flamingo          | —                               |
| `5`      | Banana (Amarillo) | 🟡 **Revisión / Presupuesto**  |
| `6`      | Tangerine (Naranja)| 🟠 **Mantenimiento / Reparación** |
| `7`      | Peacock           | —                               |
| `8`      | Graphite (Gris)   | ⚪ **Otro**                    |
| `9`      | Blueberry (Azul)  | 🔵 **Instalación**             |
| `10`     | Basil             | —                               |
| `11`     | Tomato            | —                               |

## Implementación del Mapping

```python
from src.db.models import TipoServicio

SERVICE_COLOR_MAP: dict[str, str] = {
    TipoServicio.INSTALACION.value: "9",    # Blueberry (azul)
    TipoServicio.REVISION.value: "5",       # Banana (amarillo)
    TipoServicio.MANTENIMIENTO.value: "6",  # Tangerine (naranja)
    TipoServicio.REPARACION.value: "6",     # Tangerine (naranja)
    TipoServicio.PRESUPUESTO.value: "5",    # Banana (amarillo)
    TipoServicio.OTRO.value: "8",           # Graphite (gris)
}

# Color para eventos con EstadoEvento.COMPLETADO (aplicado al completar, no por tipo)
COMPLETED_COLOR = "2"  # Sage (verde)


def get_color_for_service(tipo: str) -> str:
    """Retorna el color ID de Google Calendar para un tipo de servicio."""
    return SERVICE_COLOR_MAP.get(tipo, "8")  # Default: gris
```

## Notas

- Al completar un evento (cambiar `EstadoEvento` a `COMPLETADO`), se aplica `COMPLETED_COLOR` ("2", verde).
- El mapa de colores es centralizado para mantener consistencia.
- Si se agregan nuevos tipos de servicio, basta con agregar al dict.
