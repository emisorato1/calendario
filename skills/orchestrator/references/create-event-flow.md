# Flujo de Creación de Evento

## Diagrama de Flujo

```
Usuario envía mensaje
        │
        ▼
┌──────────────────┐
│ Parser LLM       │ ← Extrae entidades del texto
│ (create intent)  │
└────────┬─────────┘
         │
    ¿Datos completos?
    ┌────┴────┐
    │ NO      │ SÍ
    ▼         │
 ¿Falta día? │
 ┌──┴──┐     │
 │ SÍ  │ NO  │
 ▼     ▼     │
Preguntar  ¿Falta hora?    │
"¿Para qué ┌──┴──┐         │
fecha?"  │ SÍ  │ NO       │
         ▼     ▼           ▼
  Mostrar  Continuar ┌──────────────────┐
  botones  con flujo │ Buscar cliente   │ ← Búsqueda fuzzy
  horarios  normal   │ en la BD         │
  disponibles        └────────┬─────────┘
                              │
                        ¿Existe?
                     ┌────┴────┐
                     │ NO      │ SÍ
                     ▼         ▼
              ┌────────────┐  Usar cliente
              │ Crear      │  existente
              │ cliente    │
              └─────┬──────┘
                    │
                    ▼
          ┌──────────────────┐
          │ Verificar        │ ← ¿Hay otro evento en ese horario?
          │ disponibilidad   │
          └────────┬─────────┘
                   │
         ¿Prioridad alta?
         ┌────┴────┐
         │ SÍ      │ NO
         ▼         ▼
    Ignorar    ¿Disponible?
    conflicto  ┌────┴────┐
         │     │ NO      │ SÍ
         │     ▼         │
         │  Mostrar      │
         │  horarios     │
         │  disponibles  │
         │  (o pedir     │
         │   otro día)   │
         │               │
         └──────┬────────┘
                ▼
       ┌──────────────────┐
       │ Mostrar resumen  │ ← Tipo de servicio SIEMPRE visible
       │ y pedir          │   (nunca "Sin tipo")
       │ confirmación     │
       └────────┬─────────┘
                │
         ¿Confirma?
         ┌────┴────┐
         │ NO      │ SÍ
         ▼         ▼
      Cancelar ┌──────────────────┐
               │ Crear evento     │ ← SQLite + Google Calendar
               │ (BD + Calendar)  │
               └────────┬─────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ Confirmar al     │
               │ usuario          │
               └──────────────────┘
```

## Implementación

```python
from datetime import date, time, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from src.core.exceptions import ScheduleConflictError

# Result y ResultStatus se definen en error-handling.md
# from .result import Result, ResultStatus, AvailableSlot

# Validaciones se definen en date-resolution.md
# from .date_resolution import (
#     validate_event_date, validate_event_datetime, validate_work_hours,
# )


TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


class Orchestrator:
    def __init__(self, repository, calendar_client, llm_parser, settings):
        self.repo = repository
        self.calendar = calendar_client
        self.parser = llm_parser
        self.settings = settings

    async def create_event_from_text(
        self, text: str, user_id: int
    ) -> "Result":
        """Flujo completo de creación de evento desde texto natural."""
        
        # 1. Parsear el mensaje
        parsed = await self.parser.parse_create_event(text)
        
        # 2. Si falta la fecha, preguntar SOLO por la fecha (nunca asumir "hoy")
        if parsed.fecha is None:
            return Result.needs_clarification(
                question="¿Para qué fecha es el evento?"
            )
        
        # 3. Si tiene fecha pero falta la hora:
        #    a) Validar que la fecha no sea pasada
        #    b) Calcular y devolver slots disponibles
        if parsed.has_date_but_no_time:
            date_ok, date_msg = validate_event_date(parsed.fecha)
            if not date_ok:
                return Result.error(message=date_msg)
            
            slots = await self._get_available_slots(parsed.fecha)
            if not slots:
                return Result.needs_clarification(
                    question=(
                        f"No hay horarios disponibles para el "
                        f"{parsed.fecha.strftime('%d/%m/%Y')}. "
                        f"¿Querés elegir otro día?"
                    ),
                )
            return Result(
                status=ResultStatus.NEEDS_INPUT,
                question="Elegí un horario disponible:",
                data={"available_slots": slots},
            )
        
        # 4. Si faltan otros datos → preguntar
        if parsed.needs_clarification:
            return Result.needs_clarification(
                question=parsed.clarification_question,
            )
        
        # 5. Validar fecha+hora (no pasada, dentro del horario laboral)
        dt_ok, dt_msg = validate_event_datetime(parsed.fecha, parsed.hora)
        if not dt_ok:
            return Result.error(message=dt_msg)
        
        wh_ok, wh_msg = validate_work_hours(
            parsed.hora,
            parsed.duracion_minutos or 60,
            parsed.fecha.weekday(),
            self.settings,
        )
        if not wh_ok:
            return Result.error(message=wh_msg)
        
        # 6. Buscar o crear cliente
        cliente = await self._resolve_cliente(parsed)
        
        # 7. Verificar disponibilidad (con bypass si es prioridad alta)
        if not parsed.is_high_priority:
            conflict = await self._check_availability(
                parsed.fecha, parsed.hora, parsed.duracion_minutos
            )
            if conflict:
                slots = await self._get_available_slots(parsed.fecha)
                if not slots:
                    return Result(
                        status=ResultStatus.CONFLICT,
                        message=(
                            f"Ya hay un evento agendado a esa hora ({conflict}). "
                            f"No quedan horarios disponibles para ese día. "
                            f"¿Querés elegir otro día?"
                        ),
                    )
                return Result(
                    status=ResultStatus.CONFLICT,
                    message=(
                        f"Ya hay un evento agendado a esa hora ({conflict}). "
                        f"Estos son los horarios disponibles:"
                    ),
                    data={"available_slots": slots},
                )
        
        # 8. Preparar evento (sin guardar todavía — esperar confirmación)
        from src.db.models import Evento, Prioridad
        
        evento_model = Evento(
            cliente_id=cliente.id,
            tipo_servicio=parsed.tipo_servicio,
            prioridad=parsed.prioridad,
            fecha_hora=parsed.datetime,
            duracion_minutos=parsed.duracion_minutos or 60,
            notas=parsed.notas,
        )
        
        # 9. Devolver evento listo para confirmación (NO se guarda aún)
        return Result.success(
            data={
                "evento": evento_model,
                "cliente": cliente,
                "parsed": parsed,
            },
            message="Evento listo para confirmar.",
        )

    async def save_confirmed_event(
        self, evento: "Evento", cliente: "Cliente", parsed=None
    ) -> "Result":
        """
        Guarda un evento ya confirmado por el usuario.
        
        Se llama SOLO después de que el usuario presionó "Confirmar" en el
        handler. Hace: BD insert + Google Calendar create (transaccional).
        """
        # 1. Crear en BD
        evento_id = await self.repo.create_evento(evento)
        evento.id = evento_id
        
        # 2. Crear en Google Calendar
        try:
            google_event_id = self.calendar.create_event(
                title=f"{cliente.nombre} — {cliente.telefono}",
                location=cliente.direccion or (parsed.direccion if parsed else "") or "",
                description=build_event_description(parsed) if parsed else "",
                start_datetime=evento.fecha_hora,
                color_id=get_color_for_service(evento.tipo_servicio),
            )
            await self.repo.update_evento(
                evento.id, google_event_id=google_event_id
            )
        except Exception as e:
            # Rollback: eliminar de la BD si Calendar falla
            await self.repo.delete_evento(evento.id)
            return Result.error(
                message=f"Error al crear en Calendar: {e}"
            )
        
        # 3. Éxito
        return Result.success(
            data=evento,
            message="Evento creado correctamente.",
        )

    async def _resolve_cliente(self, parsed) -> "Cliente":
        """
        Busca un cliente existente o crea uno nuevo.
        
        Estrategia:
        1. Si hay teléfono → buscar por teléfono (match exacto)
        2. Si hay nombre → buscar fuzzy (threshold=80)
           - Si hay 1 match con score >= 80 → usarlo
           - Si hay varios matches → devolver Result.needs_input para desambiguar
        3. Si no hay match → crear cliente nuevo
        
        Returns:
            Cliente existente o recién creado.
        """
        from src.db.models import Cliente
        
        # 1. Buscar por teléfono (exacto)
        if parsed.cliente_telefono:
            cliente = await self.repo.get_cliente_by_telefono(parsed.cliente_telefono)
            if cliente:
                return cliente
        
        # 2. Buscar por nombre (fuzzy)
        if parsed.cliente_nombre:
            matches = await self.repo.search_clientes_fuzzy(
                parsed.cliente_nombre, threshold=80, limit=3
            )
            if len(matches) == 1:
                return matches[0][0]  # (Cliente, score) → Cliente
            # Si hay múltiples matches, se podría pedir desambiguación
            # pero para el MVP se usa el mejor match
            if matches:
                return matches[0][0]
        
        # 3. Crear cliente nuevo
        new_cliente = Cliente(
            nombre=parsed.cliente_nombre or "Cliente sin nombre",
            telefono=parsed.cliente_telefono,
            direccion=parsed.direccion,
        )
        client_id = await self.repo.create_cliente(new_cliente)
        new_cliente.id = client_id
        return new_cliente

    async def _check_availability(
        self, fecha: date, hora: time, duracion: int = 60
    ) -> Optional[str]:
        """
        Verifica si un horario está disponible.
        
        Usa comparación estricta de rangos: un evento que TERMINA a las 16:00
        NO bloquea un evento que EMPIEZA a las 16:00 (consecutivos permitidos).
        
        Solo considera eventos PENDIENTES — los cancelados y completados no
        bloquean horarios.
        
        Returns:
            None si disponible, string con info del conflicto si ocupado.
        """
        from src.db.models import EstadoEvento
        
        eventos_del_dia = await self.repo.list_eventos_by_date(fecha)
        
        new_start = datetime.combine(fecha, hora, tzinfo=TIMEZONE)
        new_end = new_start + timedelta(minutes=duracion)
        
        for ev in eventos_del_dia:
            # Ignorar eventos cancelados o completados
            if ev.estado != EstadoEvento.PENDIENTE:
                continue
            
            ev_start = ev.fecha_hora
            ev_end = ev_start + timedelta(minutes=ev.duracion_minutos)
            
            # Consecutivos permitidos: usamos < y >, NO <= ni >=
            # Si new_start == ev_end → OK (consecutivo)
            # Si new_end == ev_start → OK (consecutivo)
            if new_start < ev_end and new_end > ev_start:
                return f"{ev.hora_formateada} - {ev_end.strftime('%H:%M')}"
        
        return None

    async def _get_available_slots(
        self, fecha: date, slot_duration: int = 60
    ) -> list[AvailableSlot]:
        """
        Calcula los bloques horarios disponibles para un día.
        
        Usa el horario laboral de Settings y resta los eventos existentes.
        Los horarios consecutivos (pegados a otro evento) son válidos.
        Solo considera eventos PENDIENTES para bloquear slots.
        
        Returns:
            Lista de AvailableSlot con los bloques libres del día.
        """
        from src.db.models import EstadoEvento
        
        # Determinar horario laboral del día
        weekday = fecha.weekday()
        if weekday == 6:  # Domingo
            return []  # No se trabaja
        elif weekday == 5:  # Sábado
            work_start = time.fromisoformat(self.settings.work_days_saturday_start)
            work_end = time.fromisoformat(self.settings.work_days_saturday_end)
        else:  # Lunes a Viernes
            work_start = time.fromisoformat(self.settings.work_days_weekday_start)
            work_end = time.fromisoformat(self.settings.work_days_weekday_end)
        
        # Obtener eventos activos del día (solo pendientes bloquean slots)
        todos_eventos = await self.repo.list_eventos_by_date(fecha)
        eventos = [
            ev for ev in todos_eventos
            if ev.estado == EstadoEvento.PENDIENTE
        ]
        
        # Generar todos los slots de 1 hora dentro del horario laboral
        slots = []
        current = datetime.combine(fecha, work_start, tzinfo=TIMEZONE)
        end_of_day = datetime.combine(fecha, work_end, tzinfo=TIMEZONE)
        
        while current + timedelta(minutes=slot_duration) <= end_of_day:
            slot_start = current
            slot_end = current + timedelta(minutes=slot_duration)
            
            # Verificar si este slot se superpone con algún evento
            is_free = True
            for ev in eventos:
                ev_start = ev.fecha_hora
                ev_end = ev_start + timedelta(minutes=ev.duracion_minutos)
                
                # Consecutivos permitidos (< y >, no <= ni >=)
                if slot_start < ev_end and slot_end > ev_start:
                    is_free = False
                    break
            
            if is_free:
                slots.append(AvailableSlot(
                    start=slot_start.time(),
                    end=slot_end.time(),
                ))
            
            current += timedelta(minutes=slot_duration)
        
        return slots
```

## Notas

- El flujo es **en dos pasos**: `create_event_from_text` prepara y valida,
  `save_confirmed_event` persiste. Esto permite mostrar un resumen al usuario
  y esperar confirmación antes de guardar.
- `save_confirmed_event` es **transaccional**: si Calendar falla, revierte la BD.
- La búsqueda fuzzy se usa para no duplicar clientes con nombres similares.
- **Fecha**: si no hay día explícito, se pregunta. NUNCA se asume "hoy".
- **Hora**: si falta, se calculan los slots libres y se muestran como botones.
  El usuario puede seleccionar 1, 2 o 3 bloques consecutivos.
- **Validaciones temporales**: se ejecutan en dos momentos:
  1. Cuando hay fecha pero no hora (paso 3): `validate_event_date()` rechaza
     fechas pasadas y > 90 días antes de calcular slots disponibles.
  2. Cuando hay fecha+hora (paso 5): `validate_event_datetime()` rechaza
     fecha/hora ya pasada, y `validate_work_hours()` rechaza horarios fuera
     de la jornada laboral (incluyendo domingos).
  Las funciones de validación se definen en `date-resolution.md`.
- **Consecutivos**: un evento que termina a las 16:00 deja el bloque 16:00-17:00
  como disponible. Se usa comparación estricta `<` y `>` (no `<=` ni `>=`).
- **Disponibilidad**: solo los eventos con `estado == PENDIENTE` bloquean
  horarios. Los eventos cancelados y completados se ignoran al calcular
  disponibilidad y slots libres.
- **Superposición**: si hay conflicto, se muestran horarios alternativos. Si no
  quedan horarios, se pide elegir otro día.
- **Prioridad alta**: si `parsed.is_high_priority == True`, se salta la
  verificación de disponibilidad y se permite crear el evento con superposición.
- **Resumen**: el tipo de servicio SIEMPRE aparece (nunca "Sin tipo"). El
  campo `tipo_servicio` tiene default `"otro"` y un validador que impide null.
