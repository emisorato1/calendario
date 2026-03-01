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
    ▼         ▼
Preguntar  ┌──────────────────┐
al usuario │ Buscar cliente   │ ← Búsqueda fuzzy por nombre/teléfono
           │ en la BD         │
           └────────┬─────────┘
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
    ¿Disponible?
    ┌────┴────┐
    │ NO      │ SÍ
    ▼         ▼
Sugerir   ┌──────────────────┐
horario   │ Crear evento     │ ← SQLite + Google Calendar
alternativo│ (BD + Calendar)  │
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
from dataclasses import dataclass
from typing import Optional


@dataclass
class CreateEventResult:
    """Resultado de la operación de crear evento."""
    success: bool = False
    event: Optional[dict] = None
    needs_clarification: bool = False
    question: Optional[str] = None
    error: Optional[str] = None


class Orchestrator:
    def __init__(self, repository, calendar_client, llm_parser):
        self.repo = repository
        self.calendar = calendar_client
        self.parser = llm_parser

    async def create_event_from_text(
        self, text: str, user_id: int
    ) -> CreateEventResult:
        """Flujo completo de creación de evento desde texto natural."""
        
        # 1. Parsear el mensaje
        parsed = await self.parser.parse_create_event(text)
        
        if parsed.needs_clarification:
            return CreateEventResult(
                needs_clarification=True,
                question=parsed.clarification_question,
            )
        
        # 2. Buscar o crear cliente
        cliente = await self._resolve_cliente(parsed)
        
        # 3. Verificar disponibilidad
        conflict = await self._check_availability(parsed.fecha, parsed.hora)
        if conflict:
            return CreateEventResult(
                needs_clarification=True,
                question=f"Ya hay un evento agendado a esa hora ({conflict}). "
                         f"¿Querés agendar en otro horario?",
            )
        
        # 4. Crear evento en BD
        evento = await self.repo.create_evento(
            cliente_id=cliente.id,
            tipo_servicio=parsed.tipo_servicio,
            fecha_hora=parsed.datetime,
            notas=parsed.notas,
        )
        
        # 5. Crear evento en Google Calendar
        try:
            google_event_id = self.calendar.create_event(
                title=f"{cliente.nombre} — {cliente.telefono}",
                location=cliente.direccion or parsed.direccion or "",
                description=build_event_description(parsed),
                start_datetime=parsed.datetime,
                color_id=get_color_for_service(parsed.tipo_servicio),
            )
            await self.repo.update_evento(
                evento.id, google_event_id=google_event_id
            )
        except Exception as e:
            # Rollback: eliminar de la BD si Calendar falla
            await self.repo.delete_evento(evento.id)
            return CreateEventResult(
                error=f"Error al crear en Calendar: {e}"
            )
        
        # 6. Éxito
        return CreateEventResult(
            success=True,
            event=evento,
        )
```

## Notas

- El flujo es **transaccional**: si Calendar falla, se revierte la BD.
- La búsqueda fuzzy se usa para no duplicar clientes con nombres similares.
- Si hay conflicto de horario, se sugiere un horario alternativo.
