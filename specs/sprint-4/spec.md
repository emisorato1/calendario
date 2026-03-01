# Sprint 4 — Interfaz Telegram Híbrida + Orquestador Base

> **Duración estimada**: 3-4 sesiones de trabajo  
> **Objetivo**: El bot está operativo en Telegram con la interfaz híbrida completa (menú de botones persistente + lenguaje natural), manejo de estado por conversación y el orquestador conectando todos los módulos. Implementa los flujos de **creación** y **listados**.  
> **Pre-requisito**: Sprints 1, 2 y 3 completados.

---

## Entregables

### 1. `agents/telegram_listener/filters.py`

- `AuthorizedUserFilter`: deja pasar mensajes únicamente de IDs en `ADMIN_TELEGRAM_IDS` ∪ `EDITOR_TELEGRAM_IDS`. Los demás son ignorados (sin respuesta, con log `WARNING` del `user_id`).
- `AdminOnlyFilter`: deja pasar únicamente IDs en `ADMIN_TELEGRAM_IDS`.
- `EditorOrAdminFilter`: deja pasar IDs en cualquiera de los dos grupos.
- Todas las funciones helper acceden al `Settings` singleton para hacer la verificación.
- Logging a nivel `WARNING` de cualquier intento de acción fuera de los permisos del rol (ej: un Editor intentando crear).

---

### 2. `agents/telegram_listener/keyboards.py`

#### Menú Principal Admin (ReplyKeyboard persistente)
Visto solo por la cuenta/s Admin. Muestra las 4 acciones:

```python
ADMIN_MAIN_MENU = ReplyKeyboardMarkup([
    ["📅 Crear Turno",    "📋 Listar Eventos"],
    ["✏️ Editar Evento",  "🚫 Cancelar Evento"],
], resize_keyboard=True, persistent=True)
```

#### Menú Principal Editor (ReplyKeyboard persistente)
Visto por cuentas Editor. Solo muestra las acciones permitidas:

```python
EDITOR_MAIN_MENU = ReplyKeyboardMarkup([
    ["✏️ Editar Evento", "📋 Listar Eventos"],
], resize_keyboard=True, persistent=True)
```

#### Función de conveniencia
```python
def get_main_menu(user_id: int, settings: Settings) -> ReplyKeyboardMarkup:
    """Retorna el menú correcto según el rol del usuario."""
    if settings.is_admin(user_id):
        return ADMIN_MAIN_MENU
    return EDITOR_MAIN_MENU
```

#### Teclado de Confirmación (InlineKeyboard)
Para confirmar/rechazar la creación de un evento (solo Admin llega aquí):

```python
CONFIRM_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Confirmar", callback_data="confirm"),
    InlineKeyboardButton("❌ Cancelar",  callback_data="cancel"),
]])
```

#### Teclado de Franjas Horarias (InlineKeyboard dinámico)
Generado dinámicamente cuando el bot solicita la **hora faltante** de un evento.
Muestra los rangos completos disponibles del día (inicio → fin) según el horario laboral y la duración del servicio:

```python
def build_time_slot_keyboard(
    fecha: date,
    duracion_horas: float,
    settings: Settings,
    eventos_del_dia: list[dict],
) -> InlineKeyboardMarkup:
    """
    Genera botones de RANGOS horarios disponibles para el día dado.
    Cada botón muestra: 'HH:MM - HH:MM' (inicio - fin según duración).
    - Usa WORK_SCHEDULE para determinar el rango laboral del día.
    - Excluye rangos que se solapan con eventos existentes (buffer 30 min).
    - Excluye rangos donde el evento terminaría después del cierre.
    - Agrega botón '¿Otro horario?' si el usuario quiere escribirlo manualmente.
    - Si NO hay ninguna franja disponible: NO llama a esta función, 
      usa build_day_full_keyboard() en su lugar.
    
    Ejemplo de salida (lunes, duración 2h, horario 15:00-21:00):
    [15:00 - 17:00] [16:00 - 18:00]
    [17:00 - 19:00] [18:00 - 20:00]
    [19:00 - 21:00]
    [¿Otro horario?]
    """

def build_day_full_keyboard(fecha: date) -> InlineKeyboardMarkup:
    """
    Teclado para cuando el día está completamente lleno.
    No hay franjas disponibles para el servicio.
    
    Salida:
    [📅 Elegir otro día]
    [🚨 Es urgente — agendar igual]
    """

def build_date_suggestion_keyboard() -> InlineKeyboardMarkup:
    """
    Genera botones de fechas rápidas cuando falta la fecha:
    [Hoy] [Mañana] [Sábado] [Próximo Lunes]
    [¿Otra fecha?]
    """
```

#### Teclado de Selección de Evento (InlineKeyboard dinámico)
Generado dinámicamente a partir de una lista de eventos. Usado tanto por Admin como por Editor en el flujo de edición, y por Admin en el flujo de cancelación:

```python
def build_event_selection_keyboard(eventos: list[dict]) -> InlineKeyboardMarkup:
    """Genera botones numerados [1]...[N] para seleccionar un evento de la lista."""
```

---

### 3. `agents/telegram_listener/commands.py`

| Comando | Roles | Comportamiento |
|---|:---:|---|
| `/start` | Admin + Editor | Bienvenida + menú correcto según rol |
| `/help` | Admin + Editor | Lista de capacidades adaptada al rol |
| `/status` | Solo Admin | Estado real: DB (ping), Calendar (auth check), Groq (ping), uptime |
| `/clientes` | Solo Admin | Últimos 10 clientes con nombre, teléfono y fecha del último servicio |

---

### 4. `agents/telegram_listener/handler.py`

#### Estados del ConversationHandler

```python
# Estado global
IDLE = 0

# Flujo: Creación (solo Admin)
AWAITING_CREATION_INPUT = 1   # Esperando descripción del turno
AWAITING_MISSING_DATA = 2     # Bot pide dato faltante (fecha o hora) con botones
AWAITING_CONFIRMATION = 3     # Mostrando resumen, esperando confirmar/cancelar

# Flujo: Cancelación (solo Admin)
AWAITING_CANCEL_SELECTION = 4
AWAITING_CANCEL_CONFIRM = 5

# Flujo: Edición (Admin + Editor)
AWAITING_EDIT_SELECTION = 6
AWAITING_EDIT_INSTRUCTION = 7
AWAITING_EDIT_CONFIRM = 8
```

#### Handlers por estado

| Estado | Entrada del usuario | Rol requerido | Acción |
|---|---|:---:|---|
| `IDLE` | Mensaje de texto libre | Admin + Editor | `orchestrator.process_message(text, user_role)` |
| `IDLE` | Botón `📅 Crear Turno` | **Solo Admin** | Muestra cartel de ayuda → `AWAITING_CREATION_INPUT` |
| `IDLE` | Botón `📋 Listar Eventos` | Admin + Editor | Muestra submenú de tipo de listado |
| `IDLE` | Botón `✏️ Editar Evento` | Admin + Editor | Muestra lista de eventos próximos → `AWAITING_EDIT_SELECTION` |
| `IDLE` | Botón `🚫 Cancelar Evento` | **Solo Admin** | Muestra lista de eventos próximos → `AWAITING_CANCEL_SELECTION` |
| `AWAITING_CREATION_INPUT` | Texto libre | **Solo Admin** | Parsea con LLM → si completo: resumen → `AWAITING_CONFIRMATION`; si faltan datos: `→ AWAITING_MISSING_DATA` |
| `AWAITING_MISSING_DATA` | Botón de horario O texto libre | **Solo Admin** | Completa el dato faltante → si aún faltan más: repite; si completo: resumen → `AWAITING_CONFIRMATION` |
| `AWAITING_CONFIRMATION` | `confirm` / `cancel` | **Solo Admin** | Confirmar o abortar creación |
| `AWAITING_CANCEL_SELECTION` | Número de evento | **Solo Admin** | `AWAITING_CANCEL_CONFIRM` |
| `AWAITING_CANCEL_CONFIRM` | `confirm` / `cancel` | **Solo Admin** | Eliminar o volver |
| `AWAITING_EDIT_SELECTION` | Número de evento | Admin + Editor | `AWAITING_EDIT_INSTRUCTION` |
| `AWAITING_EDIT_INSTRUCTION` | Texto libre | Admin + Editor | Parsear con LLM → `AWAITING_EDIT_CONFIRM` |
| `AWAITING_EDIT_CONFIRM` | `confirm` / `cancel` | Admin + Editor | Aplicar cambios o abortar |

#### Protección de acciones restringidas

Si un **Editor** envía texto con intención `agendar` o `cancelar`, el orquestador lo detecta y responde:
> *"No tenés permiso para realizar esa acción. Podés editar eventos y consultar la agenda."*

Si un **usuario desconocido** escribe, `AuthorizedUserFilter` lo bloquea silenciosamente.

#### Regla de timeout
Si el usuario no responde en 5 minutos en cualquier estado intermedio, volver a `IDLE` y enviar mensaje de expiración.

---

### 5. `core/orchestrator.py`

Clase `Orchestrator` — conecta todos los módulos.

#### Enum de rol

```python
class UserRole(str, Enum):
    admin = "admin"
    editor = "editor"
```

#### Métodos principales

```python
async def process_message(self, text: str, user_id: int) -> OrchestratorResponse:
    """
    Entry point para mensajes de texto libre en estado IDLE.
    1. Determina el rol del usuario (admin / editor).
    2. Parsea la intención.
    3. Verifica que el rol tenga permiso para esa intención.
    4. Si no tiene permiso: retorna mensaje de acceso denegado.
    5. Si tiene permiso: despacha al flujo correspondiente.
    """

async def start_creation_flow(
    self,
    parsed: ParsedMessage,
    context_data: dict | None = None,
) -> OrchestratorResponse:
    """
    Solo accesible para Admin.
    Analiza qué campos obligatorios faltan (fecha, hora).
    - Si falta la fecha: retorna solicitud con `build_date_suggestion_keyboard()`.
    - Si la fecha cae en domingo: informa que no hay servicio ese día.
    - Si la fecha está completa pero falta la hora:
        • Calcula franjas disponibles con `get_available_slots()`.
        • Si hay franjas: retorna `build_time_slot_keyboard()` con RANGOS.
        • Si no hay franjas (día lleno) Y NO es urgente:
            retorna `build_day_full_keyboard()` con mensaje de día lleno.
        • Si no hay franjas Y es urgente: continuarú pidiendo la hora
            igual (con `build_time_slot_keyboard()` mostrando solo '¿Otro horario?').
    - Si todo está completo: buscar/crear cliente → verificar conflictos → retornar resumen.
    El `context_data` acumula los campos ya recopilados entre iteraciones.
    El flag `context_data['urgente']` saltea el bloqueo de día lleno.
    """

async def complete_missing_field(
    self,
    field: str,
    value: str,
    context_data: dict,
) -> OrchestratorResponse:
    """
    Recibe el valor del campo que el usuario informó (por botón o texto).
    Parsea el valor con el LLM si es texto libre.
    Actualiza context_data con el nuevo valor.
    Llama a start_creation_flow() con el context_data actualizado.
    Si aún falta otro campo, dispara una nueva solicitud.
    Si está completo, avanza a AWAITING_CONFIRMATION.
    """

async def check_day_capacity(
    self,
    fecha: date,
    duracion_horas: float,
) -> tuple[bool, float]:
    """
    Verifica si el día tiene horas laborales suficientes para agregar un evento.
    Retorna: (tiene_capacidad: bool, horas_libres_restantes: float)
    
    Algoritmo:
    1. Obtener el horario laboral del día desde WORK_SCHEDULE (según weekday()).
    2. Si es domingo (None): retorna (False, 0.0).
    3. Listar eventos ya agendados ese día.
    4. Sumar sus duraciones.
    5. horas_libres = total_hours_del_dia - horas_ocupadas
    6. Retorna (horas_libres >= duracion_horas, horas_libres).
    """

async def confirm_event(self, context: CreationContext) -> OrchestratorResponse:
    """
    Post-confirmación del usuario (Admin):
    1. Crear evento en Google Calendar.
    2. Registrar servicio en historial DB.
    3. Retornar confirmación con link al evento.
    """

async def get_upcoming_events_for_selection(self) -> tuple[list[dict], str]:
    """
    Para iniciar un flujo de cancelar o editar.
    Accesible para ambos roles.
    Retorna: (lista de eventos, texto formateado para mostrar al usuario).
    """

async def resolve_list_query(self, parsed: ParsedMessage) -> str:
    """
    Resuelve cualquier tipo de intención de listado.
    Accesible para ambos roles.
    Despacha a listar_pendientes / listar_historial / listar_dia / listar_cliente.
    """
```

#### `CreationContext` (dataclass)

```python
@dataclass
class CreationContext:
    """Contexto acumulado para el flujo de creación, incluyendo datos parciales."""
    nombre_cliente: str | None = None
    tipo_servicio: str | None = None
    fecha: date | None = None
    hora: time | None = None
    duracion_horas: float | None = None
    direccion: str | None = None
    telefono: str | None = None
    cliente_obj: Cliente | None = None  # Cliente ya resuelto en DB
    campo_pendiente: str | None = None  # "fecha" o "hora" si falta algo
```

#### `OrchestratorResponse` (dataclass)

```python
@dataclass
class OrchestratorResponse:
    text: str                                      # Mensaje de texto para Telegram
    keyboard: InlineKeyboardMarkup | None = None   # Teclado inline (opcional)
    context: dict | None = None                    # Datos para guardar en user_data
    next_state: int | None = None                  # Estado al que debe avanzar el handler
```

---

### 6. `main.py`

Entry point del sistema:

1. Cargar `Settings` → fail-fast si faltan vars requeridas.
2. Configurar `structlog`.
3. Inicializar DB: correr migraciones.
4. Crear instancias de: `GroqParser`, `DBRepository`, `CalendarClient`, `Orchestrator`.
5. Construir `Application` de `python-telegram-bot`.
6. Registrar handlers con filtros por rol: `AuthorizedUserFilter`, `AdminOnlyFilter`, `ConversationHandler`, comandos.
7. Al arrancar, mostrar el menú correcto a cada usuario autorizado (Admin ve 4 botones, Editor ve 2).
8. `application.run_polling()` con graceful shutdown `SIGINT`/`SIGTERM`.

---

### 7. Tests

#### `tests/test_orchestrator.py`

- `process_message` como Admin con intención `agendar` → retorna resumen.
- `process_message` como Editor con intención `agendar` → retorna error de permiso.
- `process_message` como Editor con intención `cancelar` → retorna error de permiso.
- `process_message` como Editor con intención `editar` → flujo correcto disparado.
- `process_message` como Editor con intención `listar_pendientes` → lista retornada.
- `confirm_event` → crea evento en Calendar (mock) + registra en DB (mock).
- `get_upcoming_events_for_selection` → lista formateada con botones numerados.
- `resolve_list_query` despacha correctamente según intención.

#### `tests/test_telegram_listener/test_filters.py`

- Usuario no registrado → `AuthorizedUserFilter` bloquea y loguea `WARNING`.
- Admin ID configurado → `AdminOnlyFilter` deja pasar.
- Editor ID → `AdminOnlyFilter` bloquea.
- Editor ID → `EditorOrAdminFilter` deja pasar.

#### `tests/test_telegram_listener/test_keyboards.py`

- `get_main_menu` con Admin ID → retorna `ADMIN_MAIN_MENU` (4 botones).
- `get_main_menu` con Editor ID → retorna `EDITOR_MAIN_MENU` (2 botones).

#### `tests/test_telegram_listener/test_handler.py`

- Usuario Editor en `IDLE` presiona `🚫 Cancelar Evento` → mensaje de acceso denegado.
- Usuario Editor en `IDLE` envía texto con intención `agendar` → mensaje de acceso denegado.
- Usuario Editor en `IDLE` presiona `✏️ Editar Evento` → flujo de edición iniciado.
- Usuario Admin en `IDLE` presiona `🚫 Cancelar Evento` → lista de eventos próximos.
- Callback `confirm` en `AWAITING_CONFIRMATION` por Admin → `confirm_event` llamado.
- Timeout de conversación → retorno a `IDLE` con mensaje.

---

## Flujo Completo: Creación con dato faltante (ejemplo)

```
Usuario: [presiona 📅 Crear Turno]
Bot: 📅 *Nuevo turno*

     Contáme sobre el turno que querés agendar.
     Podés escribir de forma natural, por ejemplo:

     • "Instalación de cámaras en lo de García el lunes a las 10"
     • "Revisión en casa de López, mañana 14:00"
     • "Presupuesto para Martínez, viernes 9:30"

     💡 Cuanto más detallés (cliente, servicio, fecha, hora), más rápido lo proceso.

Usuario: "Revisión en lo de García el martes"
Bot: ⏳ Procesando...
Bot: 🕒 *¿A qué hora querés agendar la revisión del martes?*

     Horarios disponibles:
     [15:00] [16:00] [17:00]
     [18:00] [19:00] [20:00]
     [¿Otro horario?]

Usuario: [16:00]
Bot: ⏳ Procesando...
Bot: 📋 *Resumen del evento*
     🔧 Tipo: Revisión
     👤 Cliente: García, Juan (recurrente ✅)
     📅 Fecha: Martes 03/03/2026
     🕐 Hora: 16:00 - 17:00 (1h)
     📍 Dirección: Av. San Martín 456 (de BD)
     📞 Teléfono: 260-4567890 (de BD)
     🎨 Color: 🟡 Amarillo
     ¿Confirmar este evento?
     [✅ Confirmar] [❌ Cancelar]
Usuario: [✅ Confirmar]
Bot: ✅ Evento creado exitosamente.
     📅 Revisión para García, Juan
     🔗 [Ver en Calendar](https://...)
```

---

## Criterios de Aceptación

- [ ] El bot responde SOLO a IDs en `ADMIN_TELEGRAM_IDS` y `EDITOR_TELEGRAM_IDS`.
- [ ] Admin ve `ADMIN_MAIN_MENU` (4 botones), Editor ve `EDITOR_MAIN_MENU` (2 botones).
- [ ] Al presionar `📅 Crear Turno`, el bot muestra el cartel de ayuda antes de esperar input.
- [ ] Si falta la **hora**: el bot pregunta con botones de franjas horárias disponibles del día.
- [ ] Si falta la **fecha**: el bot pregunta con botones de fechas rápidas (Hoy, Mañana, Sábado, etc.).
- [ ] Si falta la **hora y la fecha**: pide primero la fecha, luego la hora.
- [ ] Si el usuario elige `¿Otro horario?` o `¿Otra fecha?`, acepta texto en lenguaje natural.
- [ ] Domingos: el bot informa que no hay servicio ese día y no permite agendar.
- [ ] Flujo de creación con confirmación funciona end-to-end.
- [ ] Si el usuario cancela con `❌`, el evento NO se crea.
- [ ] `/status` muestra el estado real de DB, Calendar y Groq (solo Admin).
- [ ] Mensajes de usuarios no autorizados se loguean y se ignoran.
- [ ] Editor que intenta crear o cancelar recibe mensaje de acceso denegado.
- [ ] `SIGINT` cierra conexiones limpiamente.
- [ ] El bot reconecta automáticamente si pierde conexión.
- [ ] Timeout de conversación vuelve a `IDLE` con mensaje.

---

## Dependencias Nuevas

```
python-telegram-bot>=21.0
```
