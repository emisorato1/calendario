# Sprint 4 — Bot de Telegram

## Descripción

Implementar el bot de Telegram completo: comando `/start` y `/menu`, menú
de botones inline adaptado por rol, handlers de conversación para cada acción,
handler de lenguaje natural (sin botones), verificación de permisos y
formateo de respuestas.

## Objetivos

- [ ] Configurar la `Application` de `python-telegram-bot`.
- [ ] Implementar middleware de autenticación y permisos por rol.
- [ ] Implementar `/start` y `/menu` con menú de botones inline.
- [ ] Implementar `ConversationHandler` para cada acción.
- [ ] Implementar handler de texto libre (delega al LLM).
- [ ] Implementar formateo de respuestas (eventos, contactos, confirmaciones).
- [ ] Implementar keyboards dinámicos (listas de eventos, contactos).
- [ ] Manejar timeouts de conversaciones abandonadas.
- [ ] Implementar recepción de fotos para cierre de servicio.

## Requisitos Técnicos

| Requisito            | Detalle                                           |
| -------------------- | ------------------------------------------------- |
| Librería             | `python-telegram-bot` v20+                        |
| Modo                 | Polling (no webhooks)                             |
| Permisos             | Por `TELEGRAM_ID` configurado en `.env`           |
| Conversaciones       | `ConversationHandler` con timeout de 5 min        |
| Formato de mensajes  | Markdown con emojis                               |
| Fotos                | Recibir y almacenar en cierre de servicio         |

## Pasos de Implementación

### 1. Aplicación (`src/bot/app.py`)

- Crear `Application` con `ApplicationBuilder`.
- Registrar todos los handlers.
- Inyectar `Orchestrator` en `context.bot_data`.
- Configurar error handler global.
- Iniciar polling.

### 2. Middleware de Permisos (`src/bot/middleware.py`)

```python
@require_role("admin")
async def handler(update, context):
    ...

@require_role("admin", "editor")
async def handler(update, context):
    ...
```

- Decorador `require_role()` que verifica `TELEGRAM_ID` contra la config.
- Si no autorizado: responde "🚫 No tenés permiso" y retorna.
- Loguear intentos de acceso denegado.

### 3. Comando `/start` y `/menu` (`src/bot/handlers/start.py`)

- Mensaje de bienvenida con nombre del usuario.
- Menú de botones inline adaptado al rol.
- Botones visibles según permisos (admin ve todo, editor ve subset).

### 4. Handlers de Conversación

Un `ConversationHandler` por acción:

| Handler                              | Entry Point            | Estados                              |
| ------------------------------------ | ---------------------- | ------------------------------------ |
| `crear_evento.py`                    | Botón "📝 Crear"       | DESCRIPTION → DATE → TIME_SLOT → CONFIRM |
| `editar_evento.py`                   | Botón "✏️ Editar"      | SELECT → CHANGES → CONFIRM           |
| `ver_eventos.py`                     | Botón "📋 Ver"         | (sin estados, inmediato)             |
| `eliminar_evento.py`                 | Botón "🗑️ Eliminar"   | SELECT → CONFIRM                     |
| `terminar_evento.py`                 | Botón "✅ Terminar"    | SELECT → CLOSURE → PHOTOS → CONFIRM |
| `contactos.py` (ver)                 | Botón "👥 Ver"         | (sin estados, inmediato)             |
| `contactos.py` (editar)             | Botón "✏️ Editar"      | SELECT → FIELD → VALUE → CONFIRM     |

### 5. Handler Natural (`src/bot/handlers/natural.py`)

- Captura **todo** texto libre que no sea comando ni parte de una conversación.
- Envía al `Orchestrator.handle_natural_message(text, user_id)`.
- El orquestador detecta intención con el LLM y ejecuta la acción correspondiente.
- Si la intención es ambigua, muestra el menú de botones como ayuda.

### 6. Formateo (`src/bot/formatters.py`)

- `format_events_list(events_by_day)`: Eventos agrupados por día con emojis.
- `format_event_confirmation(event)`: Confirmación con todos los datos.
- `format_contacts_list(contacts)`: Lista de contactos con dirección.
- `format_event_detail(event)`: Detalle completo de un evento.
- `format_closure_confirmation(event)`: Confirmación de cierre.

### 7. Keyboards (`src/bot/keyboards.py`)

- `build_main_menu(role)`: Menú principal adaptado al rol.
- `build_event_list_keyboard(events)`: Lista de eventos seleccionables.
- `build_contact_list_keyboard(contacts)`: Lista de contactos seleccionables.
- `build_confirmation_keyboard()`: Botones Confirmar / Cancelar.
- `build_field_selection_keyboard()`: Selección de campo a editar.
- `build_time_slots_keyboard(slots, selected)`: Botones de horarios disponibles
  del día. Soporta multi-selección (1-3 bloques consecutivos). Los slots ya
  seleccionados se muestran con un check mark.

### 8. Constantes (`src/bot/constants.py`)

- Textos de mensajes del bot centralizados.
- Estados de `ConversationHandler`.
- Emojis por tipo de servicio.

### 9. Tests

- `tests/unit/test_formatters.py`: Verificar formato de respuestas.
- `tests/unit/test_keyboards.py`: Verificar generación de botones por rol.
- `tests/unit/test_middleware.py`: Verificar permisos admin/editor/denegado.

## Criterios de Aceptación

- [ ] `/start` muestra bienvenida y menú adaptado al rol.
- [ ] Admin ve todos los botones; Editor ve subset limitado.
- [ ] Usuarios no autorizados reciben mensaje de acceso denegado.
- [ ] Cada flujo de conversación funciona de principio a fin.
- [ ] El handler de texto libre detecta intenciones correctamente.
- [ ] Las respuestas muestran emojis y formato prolijo.
- [ ] Conversaciones abandonadas expiran a los 5 minutos.
- [ ] Se pueden enviar fotos en el flujo de cierre.
- [ ] El flujo de crear evento tiene estados DESCRIPTION → DATE → TIME_SLOT → CONFIRM.
- [ ] Cuando falta la hora, se muestran botones inline con horarios disponibles.
- [ ] El usuario puede seleccionar 1, 2 o 3 bloques horarios consecutivos.
- [ ] El resumen de confirmación SIEMPRE muestra el tipo de servicio (nunca "Sin tipo").
- [ ] Todos los tests pasan.

## Skills Referenciadas

- [Telegram Bot](../../skills/telegram-bot/SKILL.md)
  - [Estructura de Handlers](../../skills/telegram-bot/references/handler-structure.md)
  - [Menú y Botones Inline](../../skills/telegram-bot/references/menu-buttons.md)
  - [ConversationHandler Patterns](../../skills/telegram-bot/references/conversation-patterns.md)
  - [Formato de Respuestas](../../skills/telegram-bot/references/response-formatting.md)
