# Resolución de Fechas Relativas

## Problema

Los usuarios hablan de fechas de forma natural: "mañana", "el viernes",
"la semana que viene", "pasado mañana a las 16". El LLM debe resolver
estas expresiones a fechas concretas.

## Regla Fundamental: NUNCA asumir "hoy"

Si el usuario **no menciona explícitamente un día**, el LLM NO debe asumir
que es para "hoy". Debe devolver `fecha=null` y preguntar por la fecha.

**Expresiones que SÍ cuentan como día explícito:**
- "hoy", "mañana", "pasado mañana"
- "el lunes", "el viernes", "el sábado"
- "la semana que viene"
- "el 15", "el 3 de marzo"
- "en 3 días"

**Expresiones que NO cuentan como día explícito:**
- "a las 16" (sin día → preguntar fecha)
- "a la tarde" (sin día → preguntar fecha)
- "instalación para García" (sin día → preguntar fecha)

## Estrategia

1. Incluir **siempre** la fecha y día actuales en el prompt del sistema.
2. Dejar que el LLM resuelva la fecha relativa a una fecha absoluta.
3. Validar la fecha resuelta en el backend (no puede ser pasada).
4. **Si no hay día explícito → `fecha=null`, `missing_fields=["fecha"]`**.

## Expresiones Comunes (Argentina)

| Expresión               | Resolución                             |
| ----------------------- | -------------------------------------- |
| "hoy"                   | Fecha actual (explícito)               |
| "mañana"                | Fecha actual + 1 día                   |
| "pasado mañana"         | Fecha actual + 2 días                  |
| "el lunes" (futuro)     | Próximo lunes                          |
| "el viernes a las 10"   | Próximo viernes, 10:00                 |
| "la semana que viene"   | Próximo lunes                          |
| "en 3 días"             | Fecha actual + 3                       |
| "a las 16" (sin día)    | **fecha=null** → preguntar fecha       |
| "a la tarde" (sin día)  | **fecha=null** → preguntar fecha       |

## Flujo Secuencial de Preguntas

Cuando faltan datos de fecha y/o hora, el sistema sigue un orden estricto:

```
¿Tiene día explícito?
├─ NO → preguntar: "¿Para qué fecha es el evento?"
│        (NO preguntar hora todavía)
│        ↓ usuario responde con día
│        ¿Tiene hora?
│        ├─ NO → mostrar botones con horarios disponibles del día
│        └─ SÍ → continuar con el flujo normal
│
└─ SÍ → ¿Tiene hora?
         ├─ NO → mostrar botones con horarios disponibles del día
         └─ SÍ → continuar con el flujo normal (datos completos)
```

## Validaciones Post-LLM

```python
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def validate_event_date(event_date: date) -> tuple[bool, str]:
    """
    Valida que la fecha del evento no sea pasada ni demasiado lejana.
    Se llama ANTES de pedir la hora (cuando solo se tiene la fecha).
    
    Returns:
        (es_válido, mensaje_de_error)
    """
    today = datetime.now(TIMEZONE).date()
    
    if event_date < today:
        return False, "Esa fecha ya pasó. ¿Para qué día querés agendar?"
    
    if event_date > today + timedelta(days=90):
        return False, "No se pueden agendar eventos con más de 90 días de anticipación."
    
    return True, ""


def validate_event_datetime(
    event_date: date, event_time: time
) -> tuple[bool, str]:
    """
    Valida que la fecha/hora del evento sea válida.
    Se llama cuando ya se tienen tanto fecha como hora.
    
    Returns:
        (es_válido, mensaje_de_error)
    """
    now = datetime.now(TIMEZONE)
    event_dt = datetime.combine(event_date, event_time, tzinfo=TIMEZONE)
    
    if event_dt < now:
        return False, (
            "La fecha y hora del evento ya pasaron. "
            "¿Querés agendar para otro momento?"
        )
    
    if event_dt > now + timedelta(days=90):
        return False, (
            "No se pueden agendar eventos con más de 90 días de anticipación."
        )
    
    return True, ""


def validate_work_hours(
    event_time: time,
    duracion_minutos: int,
    weekday: int,
    settings,
) -> tuple[bool, str]:
    """
    Valida que el horario del evento esté dentro del horario laboral.
    
    Args:
        event_time: Hora de inicio del evento.
        duracion_minutos: Duración del evento en minutos.
        weekday: Día de la semana (0=lunes, 6=domingo).
        settings: Instancia de Settings con horarios laborales.
    
    Returns:
        (es_válido, mensaje_de_error)
    """
    if weekday == 6:  # Domingo
        return False, "No se atiende los domingos. ¿Querés elegir otro día?"
    
    if weekday == 5:  # Sábado
        work_start = time.fromisoformat(settings.work_days_saturday_start)
        work_end = time.fromisoformat(settings.work_days_saturday_end)
        dia = "sábados"
    else:  # Lunes a Viernes
        work_start = time.fromisoformat(settings.work_days_weekday_start)
        work_end = time.fromisoformat(settings.work_days_weekday_end)
        dia = "lunes a viernes"
    
    event_end = (
        datetime.combine(date.today(), event_time)
        + timedelta(minutes=duracion_minutos)
    ).time()
    
    if event_time < work_start or event_end > work_end:
        return False, (
            f"El horario laboral de {dia} es de "
            f"{work_start.strftime('%H:%M')} a {work_end.strftime('%H:%M')}. "
            f"¿Querés elegir otro horario?"
        )
    
    return True, ""
```

## Notas

- Si el usuario dice "a la tarde" sin hora específica y sin día, preguntar primero el día.
- Si el usuario dice "el lunes" y hoy es lunes, interpretar como el próximo lunes
  (a menos que no haya pasado la hora del evento).
- Configurar la zona horaria correcta en el prompt para evitar confusiones.
- **NUNCA** asumir "hoy" como default cuando el día no se menciona explícitamente.
- Cuando falta la hora pero hay día, el **Orquestador** calcula los horarios
  disponibles y el **handler** los muestra como botones inline. El LLM NO
  participa en la selección de hora en este caso.
