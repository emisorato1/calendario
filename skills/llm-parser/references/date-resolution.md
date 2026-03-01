# Resolución de Fechas Relativas

## Problema

Los usuarios hablan de fechas de forma natural: "mañana", "el viernes",
"la semana que viene", "pasado mañana a las 16". El LLM debe resolver
estas expresiones a fechas concretas.

## Estrategia

1. Incluir **siempre** la fecha y día actuales en el prompt del sistema.
2. Dejar que el LLM resuelva la fecha relativa a una fecha absoluta.
3. Validar la fecha resuelta en el backend (no puede ser pasada).

## Expresiones Comunes (Argentina)

| Expresión               | Resolución           |
| ----------------------- | -------------------- |
| "hoy"                   | Fecha actual          |
| "mañana"                | Fecha actual + 1 día |
| "pasado mañana"         | Fecha actual + 2 días |
| "el lunes" (futuro)     | Próximo lunes         |
| "el viernes a las 10"   | Próximo viernes, 10:00 |
| "la semana que viene"   | Próximo lunes         |
| "en 3 días"             | Fecha actual + 3      |
| "a las 16"              | Hoy a las 16:00 (si no pasó) |
| "a la tarde"            | Hoy entre 14-17 (pedir hora exacta) |

## Validaciones Post-LLM

```python
from datetime import datetime, date
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def validate_event_datetime(event_date: date, event_time: time) -> tuple[bool, str]:
    """
    Valida que la fecha/hora del evento sea válida.
    
    Returns:
        (es_válido, mensaje_de_error)
    """
    now = datetime.now(TIMEZONE)
    event_dt = datetime.combine(event_date, event_time, tzinfo=TIMEZONE)
    
    if event_dt < now:
        return False, "La fecha y hora del evento ya pasaron. ¿Querés agendar para otro momento?"
    
    if event_dt > now + timedelta(days=90):
        return False, "No se pueden agendar eventos con más de 90 días de anticipación."
    
    return True, ""
```

## Notas

- Si el usuario dice "a la tarde" sin hora específica, el bot debe preguntar la hora exacta.
- Si el usuario dice "el lunes" y hoy es lunes, interpretar como el próximo lunes
  (a menos que no haya pasado la hora del evento).
- Configurar la zona horaria correcta en el prompt para evitar confusiones.
