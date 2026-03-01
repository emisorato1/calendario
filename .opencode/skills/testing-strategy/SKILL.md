---
name: testing-strategy
description: Estrategia completa de testing con Pytest, fixtures, mocking y cobertura ≥ 80%. Activar cuando se creen tests, configuren fixtures, o se trabaje en cobertura de código.
---

# Skill de Estrategia de Testing

## 📋 Propósito

Establecer una estrategia de testing robusta para el Agente Calendario, con objetivo de ≥ 80% de cobertura y tests en todas las capas. Cubre los 5 sprints completos, incluyendo los flujos interactivos de cancelación/edición y el motor de consultas.

---

## 🧪 Estructura Completa de Tests

```
tests/
├── __init__.py
├── conftest.py                          # Fixtures globales
├── test_config_and_core.py              # Settings, constants, logger, exceptions
│
├── test_db_manager/
│   ├── __init__.py
│   ├── test_connection.py               # Conexión async, WAL mode, foreign keys
│   ├── test_migrations.py              # Idempotencia de migraciones
│   ├── test_repository.py              # CRUD + fuzzy search + cache
│   └── test_models.py                  # Dataclasses Cliente y Servicio
│
├── test_groq_parser/
│   ├── __init__.py
│   ├── test_schemas.py                 # ParsedMessage, EditInstruction, validadores
│   ├── test_parser.py                  # parse_message + parse_edit_instruction
│   ├── test_client.py                  # Reintentos, fallback, timeout
│   └── test_prompts.py                 # build_parse_prompt, build_edit_prompt
│
├── test_calendar_sync/
│   ├── __init__.py
│   ├── test_event_builder.py           # build_event + build_patch
│   ├── test_conflict_checker.py        # Detección de conflictos + suggest_alternatives
│   ├── test_colors.py                  # COLOR_MAP + get_color_emoji
│   ├── test_formatter.py               # format_event_summary + format_event_list_item
│   └── test_client.py                  # CRUD de eventos, reintentos, búsquedas
│
├── test_telegram_listener/
│   ├── __init__.py
│   ├── test_filters.py                 # AdminFilter + logging de accesos no autorizados
│   ├── test_keyboards.py               # build_event_selection_keyboard + teclados fijos
│   ├── test_commands.py                # /start, /help, /status, /clientes
│   └── test_handler.py                 # ConversationHandler: todos los estados y flujos
│
└── test_orchestrator.py                 # Flujo completo end-to-end (todos los métodos)
```

---

## 🔧 Fixtures Clave (`conftest.py`)

### DB en Memoria

```python
@pytest.fixture
async def db_connection():
    """SQLite in-memory para tests rápidos, con migraciones aplicadas."""
    async with aiosqlite.connect(":memory:") as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await run_migrations(db)
        yield db
```

### Mock de Settings

```python
@pytest.fixture
def mock_settings():
    """Settings con valores de test, no requiere .env real."""
    from config.settings import Settings
    return Settings(
        telegram_bot_token="test_token_123",
        admin_telegram_ids=[123456789, 987654321],  # Hasta 2 admins
        editor_telegram_ids=[111222333],             # 1+ editors
        groq_api_key="test_groq_key",
        google_calendar_id="test@group.calendar.google.com",
        google_service_account_path="/fake/path/service_account.json",
        sqlite_db_path=":memory:",
        _env_file=None,
    )

@pytest.fixture
def mock_settings_admin_only():
    """Settings con solo un admin y sin editors."""
    from config.settings import Settings
    return Settings(
        telegram_bot_token="test_token_123",
        admin_telegram_ids=[123456789],
        editor_telegram_ids=[],
        groq_api_key="test_groq_key",
        google_calendar_id="test@group.calendar.google.com",
        google_service_account_path="/fake/path/service_account.json",
        sqlite_db_path=":memory:",
        _env_file=None,
    )
```

### Mock de Groq — ParsedMessage válido

```python
@pytest.fixture
def mock_groq_response_agendar():
    """Respuesta mock de Groq para intención 'agendar'."""
    return json.dumps({
        "intencion": "agendar",
        "nombre_cliente": "García",
        "tipo_servicio": "instalacion",
        "fecha": "2026-03-03",
        "hora": "10:00",
        "duracion_estimada_horas": 3.0,
        "direccion": None,
        "telefono": None,
    })
```

### Mock de Groq — EditInstruction

```python
@pytest.fixture
def mock_groq_response_edit_fecha():
    """Respuesta mock de Groq para instrucción de edición de fecha/hora."""
    return json.dumps({
        "nueva_fecha": "2026-03-06",
        "nueva_hora": "16:00",
        "nuevo_tipo_servicio": None,
        "nueva_direccion": None,
        "nuevo_telefono": None,
        "nueva_duracion_horas": None,
    })
```

### Mock de Google Calendar Client

```python
@pytest.fixture
def mock_calendar_client(mocker):
    """Mock del CalendarClient con todos los métodos async."""
    client = AsyncMock()
    client.crear_evento.return_value = {
        "id": "fake_event_id_123",
        "htmlLink": "https://calendar.google.com/fake",
        "summary": "García - 260-4567890",
    }
    client.listar_proximos_eventos.return_value = [
        {
            "id": "evt_1",
            "summary": "García, Juan - 260-111",
            "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
            "end":   {"dateTime": "2026-03-02T10:00:00-03:00"},
            "colorId": "5",
            "description": "Tipo de Servicio: revision",
        },
    ]
    client.eliminar_evento.return_value = None
    client.actualizar_evento.return_value = {"id": "evt_1", "htmlLink": "https://..."}
    return client
```

### Fixtures de Datos

```python
@pytest.fixture
def cliente_garcia():
    return Cliente(
        id_cliente=1,
        nombre_completo="García, Juan",
        alias="Juan",
        telefono="260-4567890",
        direccion="Av. San Martín 456",
        ciudad="San Rafael",
        notas_equipamiento=None,
        fecha_alta=datetime(2025, 1, 15),
    )

@pytest.fixture
def evento_proximo():
    return {
        "id": "evt_test_1",
        "summary": "García, Juan - 260-4567890",
        "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
        "end":   {"dateTime": "2026-03-02T10:00:00-03:00"},
        "location": "Av. San Martín 456",
        "colorId": "5",
        "description": "Tipo de Servicio: revision\n---\nNotas: Creado vía IA",
    }
```

---

## 📏 Reglas de Testing

1. **Nunca llamar a APIs reales** — Todo mock con `unittest.mock.AsyncMock` o `pytest-mock`.
2. **DB siempre in-memory** — No crear archivos `.db` en tests.
3. **Un assert por concepto** — Cada test verifica una sola cosa.
4. **Nombres descriptivos** — `test_buscar_cliente_fuzzy_con_typo_retorna_match`.
5. **AAA Pattern** — Arrange / Act / Assert bien separados.
6. **Fixtures sobre setup** — Usar fixtures de pytest, no `setUp()` de unittest.
7. **Cubrir happy path Y casos de error** — Cada método debe tener al menos un test de error.

---

## 🗂️ Tests Críticos por Módulo

### Settings — Sistema de Roles

```python
# test_config_and_core.py
def test_settings_admin_ids_max_2_lanza_error():
    """Más de 2 IDs en admin_telegram_ids debe fallar con ValidationError."""

def test_settings_ids_duplicados_entre_roles_lanza_error():
    """Mismo ID en admin y editor debe fallar con ValidationError."""

def test_settings_is_admin_retorna_true_para_admin():
    """is_admin(admin_id) debe retornar True."""

def test_settings_is_admin_retorna_false_para_editor():
    """is_admin(editor_id) debe retornar False."""

def test_settings_is_editor_retorna_true_para_editor():
    """is_editor(editor_id) debe retornar True."""

def test_settings_is_authorized_retorna_false_para_desconocido():
    """is_authorized(id_desconocido) debe retornar False."""

def test_settings_editor_ids_puede_estar_vacio():
    """EDITOR_TELEGRAM_IDS=[] debe ser válido."""
```

### Horario Laboral y Capacidad (`test_work_schedule.py`)

```python
def test_get_day_schedule_lunes_retorna_horario_semana(mock_settings):
    """Lunes → {start: 15:00, end: 21:00, total_hours: 6.0}."""

def test_get_day_schedule_sabado_retorna_horario_sabado(mock_settings):
    """Sábado → {start: 08:00, end: 20:00, total_hours: 12.0}."""

def test_get_day_schedule_domingo_retorna_none(mock_settings):
    """Domingo → None."""

def test_get_available_slots_sin_eventos_retorna_todos(mock_settings):
    """Lunes sin eventos: duración 2h → retorna lista de tuplas (inicio, fin) con todos los rangos posibles."""

def test_get_available_slots_excluye_franja_ocupada(mock_settings):
    """Evento 16:00-18:00 → rangos que se solapan con 16:00-18:00 no aparecen."""

def test_get_available_slots_excluye_franja_que_no_cabe(mock_settings):
    """Duración 3h en lunes: rango 19:00-22:00 no aparece (excede cierre de 21:00)."""

def test_get_available_slots_retorna_tuplas_inicio_fin(mock_settings):
    """Cada elemento de la lista es una tupla (time, time): inicio y fin del rango."""

def test_is_day_fully_booked_true_cuando_sin_franjas(mock_settings):
    """Si no hay ninguna tupla disponible → True."""

def test_is_day_fully_booked_false_con_espacios_libres(mock_settings):
    """Si quedan tuplas disponibles → False."""

def test_calculate_free_hours_dia_vacio_retorna_total(mock_settings):
    """Lunes sin eventos → 6.0 horas libres."""

def test_calculate_free_hours_descuenta_eventos(mock_settings):
    """Lunes con 2h de eventos → 4.0 horas libres."""
```

### Orquestador — Flujo de Datos Faltantes

```python
# test_orchestrator.py
async def test_start_creation_flow_sin_hora_retorna_solicitud_con_botones(
    mock_settings, mock_groq_client, mock_calendar_client
):
    """Input sin hora, día con franjas libres → OrchestratorResponse con keyboard de RANGOS (ej: '15:00 - 17:00')."""

async def test_start_creation_flow_dia_lleno_retorna_day_full_keyboard(
    mock_settings, mock_groq_client, mock_calendar_client
):
    """Día lleno (sin urgencia) → OrchestratorResponse con build_day_full_keyboard() y mensaje de otro día."""

async def test_start_creation_flow_sin_fecha_retorna_solicitud_con_botones(
    mock_settings, mock_groq_client
):
    """Input sin fecha → OrchestratorResponse con texto de solicitud y keyboard de fechas."""

async def test_start_creation_flow_domingo_retorna_error(
    mock_settings, mock_groq_client
):
    """Fecha domingo → mensaje 'sin servicio ese día', sin avanzar."""

async def test_start_creation_flow_urgente_saltea_bloqueo_dia_lleno(
    mock_settings, mock_groq_client, mock_calendar_client
):
    """context_data['urgente']=True + día lleno → bot pide hora manualmente (solo botón '¿Otro horario?')."""

async def test_complete_missing_field_hora_completa_y_muestra_resumen(
    mock_settings, mock_groq_client, mock_calendar_client
):
    """Proveer rango de hora faltante → context_data completo → OrchestratorResponse con resumen."""

async def test_complete_missing_field_otro_horario_parsea_texto_libre(
    mock_settings, mock_groq_client
):
    """Texto libre '17 y media' → LLM parsea → hora = 17:30."""

async def test_check_day_capacity_dia_lleno_retorna_false(
    mock_settings, mock_calendar_client
):
    """Día con 6h de eventos (lunes) → (False, 0.0)."""

async def test_check_day_capacity_con_espacio_retorna_true(
    mock_settings, mock_calendar_client
):
    """Día con 2h de eventos (lunes) → (True, 4.0)."""
```

### Keyboards — Franjas Horarias

```python
# test_keyboards.py
def test_build_time_slot_keyboard_lunes_sin_eventos(mock_settings):
    """Lunes sin eventos, duración 2h → botones de RANGOS ej. '15:00 - 17:00' + '¿Otro horario?'."""

def test_build_time_slot_keyboard_excluye_rangos_solapados(mock_settings):
    """Evento 15:00-17:00 → rangos que se solapan con ese bloque no aparecen."""

def test_build_time_slot_keyboard_dia_lleno_llama_day_full_keyboard(mock_settings):
    """Día completamente lleno → debe usarse build_day_full_keyboard() en lugar de esta función."""

def test_build_day_full_keyboard_tiene_boton_elegir_otro_dia():
    """build_day_full_keyboard() retorna keyboard con '📅 Elegir otro día'."""

def test_build_day_full_keyboard_tiene_boton_urgente():
    """build_day_full_keyboard() retorna keyboard con '🚨 Es urgente — agendar igual'."""

def test_build_date_suggestion_keyboard_retorna_4_opciones():
    """Keyboard de fechas rápidas tiene exactamente 4 botones + '¿Otra fecha?'."""
```

### Filters y Keyboards — Roles

```python
# test_filters.py
def test_authorized_user_filter_bloquea_desconocido(mock_settings):
    """Usuario fuera de ambas listas → filtro no pasa + log WARNING."""

def test_admin_only_filter_bloquea_editor(mock_settings):
    """Editor ID → AdminOnlyFilter no pasa."""

def test_admin_only_filter_deja_pasar_admin(mock_settings):
    """Admin ID → AdminOnlyFilter pasa."""

def test_editor_or_admin_filter_deja_pasar_editor(mock_settings):
    """Editor ID → EditorOrAdminFilter pasa."""

# test_keyboards.py
def test_get_main_menu_admin_retorna_4_botones(mock_settings):
    """Admin → ADMIN_MAIN_MENU con 4 botones (2 filas x 2)."""

def test_get_main_menu_editor_retorna_2_botones(mock_settings):
    """Editor → EDITOR_MAIN_MENU con 2 botones (1 fila x 2)."""
```

### Orquestador — Control de Permisos

```python
# test_orchestrator.py
async def test_process_message_editor_intenta_agendar_retorna_error_permiso(
    mock_settings, mock_groq_client
):
    """Editor + intención 'agendar' → mensaje de acceso denegado, sin crear evento."""

async def test_process_message_editor_intenta_cancelar_retorna_error_permiso(
    mock_settings, mock_groq_client
):
    """Editor + intención 'cancelar' → mensaje de acceso denegado."""

async def test_process_message_editor_editar_flujo_correcto(
    mock_settings, mock_groq_client
):
    """Editor + intención 'editar' → flujo de edición disparado normalmente."""

async def test_process_message_editor_listar_flujo_correcto(
    mock_settings, mock_groq_client, mock_calendar_client
):
    """Editor + intención 'listar_pendientes' → lista retornada normalmente."""
```

```python
# test_repository.py
async def test_buscar_cliente_fuzzy_con_typo_retorna_match(db_connection):
    """'Garzia' debe encontrar 'García' con score ≥ 75."""

async def test_buscar_cliente_fuzzy_sin_match_retorna_none(db_connection):
    """Nombre muy diferente no debe hacer match."""

async def test_crear_cliente_nuevo_retorna_objeto_completo(db_connection):
    """Crear cliente y verificar todos los campos del objeto retornado."""

async def test_registrar_servicio_vincula_a_cliente(db_connection, cliente_garcia):
    """El historial queda correctamente vinculado al cliente."""

async def test_actualizar_estado_servicio_a_cancelado(db_connection):
    """El estado del servicio cambia a 'cancelado'."""
```

### Groq Parser

```python
# test_schemas.py
def test_parsed_message_fecha_pasada_lanza_validation_error():
    """Fecha anterior a hoy debe fallar."""

def test_parsed_message_infiere_duracion_de_tipo_servicio():
    """Si duracion es None y tipo es 'instalacion', debe ser 3.0."""

def test_edit_instruction_sin_campos_lanza_validation_error():
    """EditInstruction con todos los campos None debe fallar."""

def test_edit_instruction_valida_con_un_campo():
    """EditInstruction con solo nueva_fecha debe ser válida."""

# test_parser.py
async def test_parse_message_intenciones_completas(mock_groq_client):
    """Probar las 8 intenciones posibles con mensajes de ejemplo."""

async def test_parse_edit_instruccion_fecha_hora(mock_groq_client):
    """'Pasalo para el viernes a las 16' → EditInstruction correcta."""

async def test_parse_edit_instruccion_tipo_servicio(mock_groq_client):
    """'Cambiá el servicio a instalación' → EditInstruction correcta."""
```

### Calendar Sync

```python
# test_event_builder.py
def test_build_event_prioriza_datos_de_db_sobre_mensaje(cliente_garcia):
    """Si el cliente tiene dirección en DB, se usa esa y no la del mensaje."""

def test_build_event_color_correcto_por_tipo_servicio():
    """instalacion → '9', revision → '5', reparacion → '6'."""

def test_build_patch_solo_incluye_campos_no_none():
    """EditInstruction con solo nueva_fecha → patch con solo start/end."""

def test_build_patch_recalcula_color_si_cambia_tipo():
    """Si EditInstruction cambia tipo de servicio, el patch incluye nuevo colorId."""

# test_formatter.py
def test_format_event_list_item_formato_correcto(evento_proximo):
    """Debe incluir número emoji, fecha, hora, emoji de color, tipo y cliente."""

def test_format_events_list_sin_eventos_retorna_mensaje_apropiado():
    """Lista vacía devuelve texto 'No hay eventos'."""
```

### Orquestador — Flujos Interactivos

```python
# test_orchestrator.py
async def test_confirm_cancel_elimina_evento_y_actualiza_db(
    mock_calendar_client, db_connection
):
    """Cancelar un evento elimina de Calendar y cambia estado en DB a 'cancelado'."""

async def test_confirm_cancel_evento_inexistente_maneja_error(mock_calendar_client):
    """event_id inválido → respuesta de error amable, sin excepción no manejada."""

async def test_parse_and_preview_edit_con_cambio_de_fecha(
    mock_groq_client, evento_proximo
):
    """Instrucción 'pasalo para el viernes' → preview muestra la nueva fecha."""

async def test_confirm_edit_aplica_patch_correcto(mock_calendar_client):
    """El patch en Calendar solo contiene los campos que cambiaron."""

async def test_listar_pendientes_formato_correcto(mock_calendar_client):
    """Retorna string con formato de lista estándar."""

async def test_listar_pendientes_sin_eventos_retorna_mensaje_apropiado(mock_calendar_client):
    """Calendar vacío → 'No tenés eventos pendientes.'"""

async def test_listar_por_dia_con_fecha_relativa(mock_calendar_client):
    """'el lunes' se resuelve a la fecha correcta."""

async def test_listar_por_cliente_usa_fuzzy_match(
    mock_calendar_client, db_connection
):
    """'garsia' debe encontrar los eventos de 'García'."""
```

### Telegram Listener — Estados

```python
# test_handler.py
async def test_boton_crear_turno_muestra_cartel_de_ayuda():
    """Presionar '📅 Crear Turno' → bot muestra cartel con ejemplos, estado = AWAITING_CREATION_INPUT."""

async def test_boton_cancelar_evento_muestra_lista_proximos():
    """Presionar '🚫 Cancelar Evento' → lista de próximos eventos."""

async def test_seleccion_fuera_de_rango_no_avanza_estado():
    """Número mayor al total de eventos → mensaje de error, mismo estado."""

async def test_cancel_confirm_elimina_evento():
    """Callback 'confirm' en AWAITING_CANCEL_CONFIRM → evento eliminado."""

async def test_cancel_abort_no_elimina_nada():
    """Callback 'cancel' en AWAITING_CANCEL_CONFIRM → sin cambios, IDLE."""

async def test_edit_instruction_llama_parse_and_preview():
    """Texto en AWAITING_EDIT_INSTRUCTION → parse_and_preview_edit llamado."""

async def test_edit_confirm_aplica_cambios():
    """Callback 'confirm' en AWAITING_EDIT_CONFIRM → confirm_edit llamado."""

async def test_submenu_listado_muestra_4_opciones():
    """Botón '📋 Listar Eventos' → submenú con 4 opciones de filtro."""
```

---

## ▶️ Comandos

```bash
# Ejecutar todos los tests
pytest -v

# Con cobertura completa
pytest --cov=agents --cov=core --cov=config --cov-report=term-missing

# Por sprint/módulo
pytest tests/test_db_manager/ -v           # Sprint 1
pytest tests/test_groq_parser/ -v          # Sprint 2
pytest tests/test_calendar_sync/ -v        # Sprint 3
pytest tests/test_telegram_listener/ tests/test_orchestrator.py -v  # Sprint 4+5

# Solo tests async
pytest -v -k "async"

# Ver cobertura en HTML
pytest --cov=agents --cov=core --cov=config --cov-report=html
```

---

## 📦 Dependencias de Test

```
pytest>=8.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
```
