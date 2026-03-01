# Coordinación BD-Calendar

## Principio

La base de datos SQLite es la **fuente de verdad**. Google Calendar es la
**vista compartida**. Toda operación debe mantener la consistencia entre ambos.

## Orden de Operaciones

### Crear Evento
```
1. Crear en SQLite (sin google_event_id)
2. Crear en Google Calendar
3. Actualizar SQLite con google_event_id
   ├─ OK → Operación completa
   └─ FALLO en Calendar → Eliminar de SQLite (rollback)
```

### Editar Evento
```
1. Actualizar en SQLite
2. Actualizar en Google Calendar
   ├─ OK → Operación completa
   └─ FALLO en Calendar → Revertir SQLite
```

### Eliminar Evento
```
1. Eliminar de Google Calendar
2. Eliminar de SQLite
   ├─ OK → Operación completa
   └─ FALLO en Calendar → Solo marcar como cancelado en SQLite
```

### Completar Evento
```
1. Actualizar BD (estado=completado, datos cierre)
2. Actualizar Calendar (color=verde, descripción cierre)
   ├─ OK → Operación completa
   └─ FALLO en Calendar → BD queda actualizada, reintentar Calendar después
```

## Implementación de Rollback

```python
async def create_event_atomic(self, evento_data, cliente):
    """Creación atómica: BD + Calendar o nada."""
    
    # Paso 1: Crear en BD
    evento_id = await self.repo.create_evento(evento_data)
    
    try:
        # Paso 2: Crear en Calendar
        google_id = await asyncio.to_thread(
            self.calendar.create_event,
            title=f"{cliente.nombre} — {cliente.telefono}",
            location=cliente.direccion,
            description=build_description(evento_data),
            start_datetime=evento_data.fecha_hora,
            color_id=get_color(evento_data.tipo_servicio),
        )
        
        # Paso 3: Vincular
        await self.repo.update_evento(evento_id, google_event_id=google_id)
        return Result.success(data={"evento_id": evento_id, "google_id": google_id})
        
    except Exception as e:
        # Rollback: eliminar de BD
        logger.error(f"Calendar falló, rollback BD: {e}")
        await self.repo.delete_evento(evento_id)
        return Result.error(f"No se pudo crear el evento en el calendario: {e}")
```

## Resiliencia

- Si Calendar está caído temporalmente, los eventos se pueden crear en la BD
  y sincronizar después con un job manual o automático.
- Un campo `sync_status` (opcional, post-MVP) puede rastrear el estado de
  sincronización de cada evento.
- Logs detallados de cada operación para facilitar debugging.
