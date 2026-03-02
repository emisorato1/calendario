# Sprint 3 — Google Calendar

## Descripción

Implementar la integración completa con Google Calendar API v3: autenticación
con Service Account, CRUD de eventos, mapeo de colores por tipo de servicio,
formato estandarizado de descripción y sincronización con la base de datos.

## Objetivos

- [ ] Configurar autenticación con Service Account.
- [ ] Implementar `GoogleCalendarClient` con CRUD de eventos.
- [ ] Implementar mapeo de colores tipo_servicio → color_id.
- [ ] Implementar templates de título, ubicación y descripción.
- [ ] Implementar actualización de evento al completar (color verde + cierre).
- [ ] Verificar conflictos de horario antes de agendar.
- [ ] Manejar errores de la API (rate limit, auth, network).

## Requisitos Técnicos

| Requisito           | Detalle                                          |
| ------------------- | ------------------------------------------------ |
| API                 | Google Calendar API v3                           |
| Auth                | Service Account (`credentials/service_account.json`) |
| Librería            | `google-api-python-client` + `google-auth`       |
| Async               | `asyncio.to_thread()` (API no es async nativa)   |
| Timezone            | `America/Argentina/Buenos_Aires`                 |
| Rate limit          | Retry con backoff exponencial                    |

## Pasos de Implementación

### 1. Autenticación (`src/calendar_api/auth.py`)

- Cargar Service Account desde `GOOGLE_SERVICE_ACCOUNT_PATH`.
- Crear credenciales con scope `https://www.googleapis.com/auth/calendar`.
- Construir servicio de Calendar API.
- Verificar conectividad al arrancar.

### 2. Cliente (`src/calendar_api/client.py`)

**Métodos:**
- `create_event(title, location, description, start, duration, color_id) → str`
  - Retorna el `google_event_id` del evento creado.
- `update_event(event_id, **updates) → bool`
  - Actualiza campos: summary, location, description, start, end, colorId.
- `delete_event(event_id) → bool`
  - Elimina un evento del calendario.
- `complete_event(event_id, closure_description) → bool`
  - Cambia color a verde y actualiza descripción con datos de cierre.
- `list_upcoming_events(max_results) → list[dict]`
  - Lista eventos futuros para verificar conflictos.
- `check_availability(start, end) → bool`
  - Verifica si hay conflictos de horario.

### 3. Mapeo de Colores (`src/calendar_api/colors.py`)

```python
SERVICE_COLOR_MAP = {
    "instalacion": "9",    # Blueberry (azul)
    "revision": "5",       # Banana (amarillo)
    "mantenimiento": "6",  # Tangerine (naranja)
    "reparacion": "6",     # Tangerine (naranja)
    "presupuesto": "5",    # Banana (amarillo)
    "otro": "8",           # Graphite (gris)
}
# COMPLETED_COLOR = "2" se aplica al cambiar EstadoEvento a COMPLETADO
```

### 4. Templates de Descripción (`src/calendar_api/templates.py`)

- `build_event_title(nombre, telefono) → str`
  - Formato: `{Nombre} — {Teléfono}`
- `build_event_description(tipo, direccion, notas) → str`
  - Con sección de post-servicio vacía para completar después.
- `build_completed_description(tipo, direccion, notas, trabajo, monto, notas_cierre, fotos) → str`
  - Con sección de post-servicio completada.

### 5. Wrapper Async (`src/calendar_api/async_wrapper.py`)

- La API de Google Calendar no es async nativa.
- Envolver llamadas con `asyncio.to_thread()` para no bloquear el event loop.

```python
async def async_create_event(self, **kwargs) -> str:
    return await asyncio.to_thread(self.create_event, **kwargs)
```

### 6. Tests

- `tests/unit/test_colors.py`: Verificar mapeo de colores.
- `tests/unit/test_templates.py`: Verificar formato de título, ubicación, descripción.
- `tests/unit/test_calendar_client.py`: Mock de la API, verificar CRUD.

## Criterios de Aceptación

- [ ] Se puede crear un evento en Google Calendar con color correcto.
- [ ] El título tiene formato `Nombre — Teléfono`.
- [ ] La descripción incluye sección de post-servicio vacía.
- [ ] Al completar, el color cambia a verde y la descripción se actualiza.
- [ ] Se detectan conflictos de horario correctamente.
- [ ] Los errores de la API se manejan sin crashear el bot.
- [ ] Todos los tests pasan.

## Skills Referenciadas

- [Google Calendar](../../skills/google-calendar/SKILL.md)
  - [CRUD de Eventos](../../skills/google-calendar/references/event-crud.md)
  - [Colores y Mapping](../../skills/google-calendar/references/color-mapping.md)
  - [Formato de Descripción](../../skills/google-calendar/references/description-format.md)
