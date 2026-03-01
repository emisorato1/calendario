# Sprint 5 — Orquestador e Integración Completa

## Descripción

Implementar el orquestador central que coordina todos los módulos (Bot, LLM,
BD, Calendar) y los flujos end-to-end. Incluye el flujo de cierre de servicio,
coordinación transaccional BD-Calendar, manejo de errores con Result pattern
y el entry point principal del sistema.

## Objetivos

- [ ] Implementar `Orchestrator` con inyección de dependencias.
- [ ] Implementar flujo completo de creación de evento (texto → BD + Calendar).
- [ ] Implementar flujo de edición de evento.
- [ ] Implementar flujo de eliminación de evento.
- [ ] Implementar flujo de cierre de servicio (terminar evento).
- [ ] Implementar flujo de ver eventos y contactos.
- [ ] Implementar flujo de edición de contacto.
- [ ] Implementar detección de intención para mensajes sin botón.
- [ ] Implementar coordinación transaccional BD ↔ Calendar (con rollback).
- [ ] Implementar Result pattern para comunicación con handlers.
- [ ] Implementar `main.py` como entry point del sistema.
- [ ] Tests de integración end-to-end.

## Requisitos Técnicos

| Requisito             | Detalle                                         |
| --------------------- | ----------------------------------------------- |
| Patrón                | Mediator / Orchestrator                         |
| Dependencias          | Repository, CalendarClient, LLMParser           |
| Coordinación          | Transaccional: si Calendar falla, rollback BD   |
| Resultados            | Result pattern (success, error, needs_input)    |
| Entry point           | `src/main.py`                                   |

## Pasos de Implementación

### 1. Result Pattern (`src/orchestrator/result.py`)

- `ResultStatus` (Enum): SUCCESS, ERROR, NEEDS_INPUT, CONFLICT.
- `Result` dataclass: status, data, message, question, errors.
- Factory methods: `Result.success()`, `Result.error()`,
  `Result.needs_clarification()`, `Result.conflict()`.

### 2. Orquestador (`src/orchestrator/orchestrator.py`)

```python
class Orchestrator:
    def __init__(
        self,
        repository: Repository,
        calendar_client: GoogleCalendarClient,
        llm_parser: LLMParser,
        settings: Settings,
    ):
        self.repo = repository
        self.calendar = calendar_client
        self.parser = llm_parser
        self.settings = settings
```

**Métodos principales:**

| Método                                | Descripción                          |
| ------------------------------------- | ------------------------------------ |
| `create_event_from_text(text, uid)`   | Texto → parse → cliente → BD → Cal  |
| `edit_event(event_id, text, uid)`     | Texto → parse edición → BD → Cal    |
| `delete_event(event_id, uid)`         | Verificar permiso → Cal → BD        |
| `complete_event(event_id, text, uid)` | Parse cierre → BD → Cal (verde)     |
| `list_pending_events()`              | Listar eventos pendientes agrupados  |
| `list_today_events()`                | Listar eventos de hoy               |
| `list_contacts()`                    | Listar todos los clientes            |
| `edit_contact(contact_id, text)`     | Parse → actualizar BD               |
| `handle_natural_message(text, uid)`  | Detectar intención → delegar         |

### 3. Flujo de Creación de Evento

1. **Parsear** texto con `parser.parse_create_event(text)`.
2. **Validar** datos completos. Si faltan → `Result.needs_clarification()`.
3. **Resolver cliente** → búsqueda fuzzy por nombre/teléfono.
   - Si existe → usar el existente.
   - Si no existe → crear nuevo en la BD.
   - Si ambiguo → preguntar al usuario.
4. **Verificar disponibilidad** del horario.
   - Si ocupado → `Result.conflict()` con sugerencia.
5. **Crear en BD** → `repo.create_evento()`.
6. **Crear en Calendar** → con color y formato correcto.
7. **Vincular** → actualizar BD con `google_event_id`.
8. **Rollback** → si Calendar falla, eliminar de BD.
9. **Retornar** → `Result.success(event)`.

### 4. Flujo de Cierre de Servicio

1. **Mostrar** eventos del día al usuario.
2. **Seleccionar** evento a completar.
3. **Solicitar** datos de cierre (trabajo, monto, notas, fotos).
4. **Parsear** con `parser.parse_closure(text)`.
5. **Actualizar BD** → estado=completado + datos de cierre.
6. **Actualizar Calendar**:
   - Color → verde (`2`).
   - Descripción → con datos de cierre completados.
7. **Confirmar** al usuario.

### 5. Manejo de Mensajes Naturales

```python
async def handle_natural_message(self, text: str, user_id: int) -> Result:
    # 1. Detectar intención
    intent = await self.parser.detect_intent(text)
    
    # 2. Verificar permisos para la intención
    if not self._check_permission(user_id, intent.intent):
        return Result.error("No tenés permiso para esta acción.")
    
    # 3. Delegar según intención
    match intent.intent:
        case Intent.CREAR_EVENTO:
            return await self.create_event_from_text(text, user_id)
        case Intent.VER_EVENTOS:
            events = await self.list_pending_events()
            return Result.success(data=events)
        case Intent.SALUDO:
            return Result.success(message="¡Hola! ¿En qué puedo ayudarte? Usá /menu para ver las opciones.")
        case Intent.DESCONOCIDO:
            return Result.needs_clarification(
                "No entendí tu mensaje. Usá /menu para ver las acciones disponibles."
            )
        case _:
            return Result.needs_clarification(
                "¿Podrías ser más específico? Decime qué querés hacer."
            )
```

### 6. Entry Point (`src/main.py`)

```python
async def main():
    # 1. Cargar y validar configuración
    settings = get_settings()
    validate_settings()
    
    # 2. Configurar logging
    setup_logging(settings.log_level, settings.log_file)
    
    # 3. Inicializar base de datos
    repository = Repository(settings.sqlite_db_path)
    await repository.connect()
    await repository.initialize()
    
    # 4. Inicializar Google Calendar
    calendar_client = GoogleCalendarClient(
        settings.google_service_account_path,
        settings.google_calendar_id,
    )
    
    # 5. Inicializar LLM Parser
    llm_parser = LLMParser(settings)
    
    # 6. Crear Orquestador
    orchestrator = Orchestrator(repository, calendar_client, llm_parser, settings)
    
    # 7. Crear y ejecutar Bot
    app = create_bot_application(settings, orchestrator)
    await app.run_polling()
```

### 7. Tests

- `tests/unit/test_result.py`: Result pattern con todos los estados.
- `tests/unit/test_orchestrator.py`: Mock de todos los componentes,
  verificar flujos completos.
- `tests/integration/test_create_event.py`: Flujo end-to-end de creación.
- `tests/integration/test_complete_event.py`: Flujo end-to-end de cierre.

## Criterios de Aceptación

- [ ] Se puede crear un evento completo desde un mensaje natural.
- [ ] Si faltan datos, el bot pregunta lo necesario.
- [ ] Si hay conflicto de horario, se informa al usuario.
- [ ] Se puede completar un evento con trabajo, monto y notas.
- [ ] Al completar, Calendar muestra color verde y descripción actualizada.
- [ ] Si Calendar falla, la BD hace rollback (no quedan datos inconsistentes).
- [ ] Los mensajes sin botón se interpretan correctamente.
- [ ] El sistema arranca con `python -m src.main` sin errores.
- [ ] Todos los tests pasan.

## Skills Referenciadas

- [Orquestador](../../skills/orchestrator/SKILL.md)
  - [Flujo de Creación](../../skills/orchestrator/references/create-event-flow.md)
  - [Manejo de Errores](../../skills/orchestrator/references/error-handling.md)
  - [Coordinación BD-Calendar](../../skills/orchestrator/references/sync-coordination.md)
- [Config & Observability](../../skills/config-observability/SKILL.md)
