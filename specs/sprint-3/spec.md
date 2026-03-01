# Sprint 3 — Integración con Google Calendar

> **Duración estimada**: 2-3 sesiones de trabajo  
> **Objetivo**: El sistema puede crear, editar y eliminar eventos en Google Calendar, detectar conflictos, buscar eventos por fecha o cliente, y aplicar colores según el tipo de servicio.  
> **Pre-requisito**: Sprint 1 y Sprint 2 completados.

---

## Entregables

### 1. `agents/calendar_sync/auth.py`

- Cargar el archivo `service_account.json` desde el path configurado en `settings.GOOGLE_SERVICE_ACCOUNT_PATH`.
- Crear credenciales con scope `https://www.googleapis.com/auth/calendar`.
- Validar que el archivo existe y tiene el formato correcto al iniciar.
- Logging de autenticación exitosa o fallida.
- Lanza `CalendarAuthError` si el archivo no existe o las credenciales son inválidas.

---

### 2. `agents/calendar_sync/client.py`

Wrapper async sobre `googleapiclient.discovery.build()`.

**Métodos requeridos:**

```python
async def crear_evento(self, evento: dict) -> dict:
    """Crea un evento y retorna el objeto completo con ID asignado."""

async def actualizar_evento(self, event_id: str, cambios: dict) -> dict:
    """PATCH parcial de un evento. Solo modifica los campos provistos."""

async def eliminar_evento(self, event_id: str) -> None:
    """Elimina un evento por ID. Lanza EventoNoEncontradoError si no existe."""

async def listar_eventos(
    self,
    time_min: datetime,
    time_max: datetime,
    max_results: int = 10
) -> list[dict]:
    """Lista eventos en un rango de fechas, ordenados por inicio."""

async def listar_proximos_eventos(self, n: int = 10) -> list[dict]:
    """Retorna los próximos N eventos desde ahora, para flujos de cancelar/editar."""

async def listar_eventos_por_fecha(self, fecha: date) -> list[dict]:
    """Todos los eventos de un día específico."""

async def buscar_eventos_por_cliente(self, nombre_cliente: str) -> list[dict]:
    """Busca eventos cuyo título contenga el nombre del cliente (fuzzy opcional)."""
```

- Reintentos con `tenacity`: 3 intentos, backoff exponencial en errores HTTP 429, 500, 503.
- Timeout configurable (default 15s).
- Logging de cada operación con duración y event_id.

---

### 3. `agents/calendar_sync/event_builder.py`

```python
def build_event(data: ParsedMessage, cliente: Cliente) -> dict:
    """Construye el dict de evento listo para la Google Calendar API."""

def build_patch(instruccion: EditInstruction, evento_actual: dict, cliente: Cliente) -> dict:
    """Construye el dict de PATCH a partir de un EditInstruction."""
```

**Reglas de `build_event`:**
- **Título**: `"{nombre_completo} - {telefono}"` (prioridad: DB > Mensaje).
- **Ubicación**: dirección del cliente (prioridad: DB > Mensaje).
- **Descripción**: formato estándar:
  ```
  Tipo de Servicio: {tipo_servicio}
  ---
  Notas: Creado vía IA
  Descripción del trabajo:
  Resultados:
  Materiales/Equipos utilizados:
  Códigos de cámaras/alarmas:
  ```
- **Start/End**: datetime con timezone `America/Argentina/Buenos_Aires`.
- **ColorId**: según `COLOR_MAP` de `constants.py`.
- **Prioridad de datos**: DB > Mensaje > Default.

**Reglas de `build_patch`:**
- Solo incluir en el dict los campos que tienen valor en `EditInstruction`.
- Si cambia el `tipo_servicio`, recalcular el `colorId`.
- Si cambia fecha/hora, recalcular `start` y `end`.

---

### 4. `agents/calendar_sync/conflict_checker.py`

```python
async def check_conflicts(
    client: CalendarClient,
    calendar_id: str,
    start: datetime,
    end: datetime,
    buffer_minutes: int = 30
) -> list[dict]:
    """
    Consulta eventos en [start - buffer, end + buffer].
    Retorna lista de eventos solapados (vacía si no hay conflictos).
    """

def suggest_alternatives(
    start: datetime,
    duration_hours: float,
    n: int = 3
) -> list[dict]:
    """
    Genera N horarios alternativos: siguiente día hábil mismo horario,
    +2h, +1 día, etc.
    """
```

---

### 5. `agents/calendar_sync/colors.py`

```python
COLOR_MAP: dict[str, str] = {
    "reparacion":    "6",   # Mandarina/Naranja
    "mantenimiento": "6",   # Mandarina/Naranja
    "instalacion":   "9",   # Arándano/Azul
    "revision":      "5",   # Plátano/Amarillo
    "presupuesto":   "5",   # Plátano/Amarillo
    "otro":          "8",   # Grafito
}

def get_color_emoji(tipo_servicio: str) -> str:
    """Retorna el emoji de color para mostrar en Telegram."""
    # "6" → "🟠", "9" → "🔵", "5" → "🟡", "8" → "⚫"
```

---

### 6. `agents/calendar_sync/formatter.py`

Módulo para formatear eventos de Calendar en texto legible para Telegram.

```python
def format_event_summary(evento: dict) -> str:
    """
    Formato para resumen de confirmación:
    🔧 Tipo: Instalación de cámaras
    👤 Cliente: Carlos García
    📅 Fecha: Martes 03/03/2026
    🕐 Hora: 10:00 - 13:00 (3h)
    📍 Dirección: Av. San Martín 456
    🎨 Color: 🔵 Azul
    """

def format_event_list_item(evento: dict, index: int) -> str:
    """
    Formato para ítem de lista numerada:
    2️⃣ Mar 03/03 | 10:00 - 13:00 | 🔵 Instalación — López, Pedro
    """

def format_events_list(eventos: list[dict], titulo: str) -> str:
    """
    Formato para lista completa:
    📅 *Eventos pendientes (5):*
    
    📌 Lun 02/03 | 09:00 - 10:00 | 🟡 Revisión — García, Juan
    ...
    """
```

---

### 7. Tests

#### `tests/test_calendar_sync/test_event_builder.py`
- `build_event` genera dict válido para la Google Calendar API.
- Colores asignados correctamente por tipo de servicio.
- Prioridad de datos: DB sobreescribe mensaje.
- Timezone aplicado correctamente.
- `build_patch` solo incluye campos presentes en `EditInstruction`.
- Si cambia tipo de servicio, se recalcula el color.

#### `tests/test_calendar_sync/test_conflict_checker.py`
- Sin eventos en rango → retorna lista vacía.
- Evento solapado → retorna ese evento.
- `suggest_alternatives` retorna exactamente 3 opciones.

#### `tests/test_calendar_sync/test_formatter.py`
- `format_event_summary` produce el texto esperado.
- `format_event_list_item` con índice correcto y emoji de color.
- `format_events_list` con 0 eventos produce mensaje apropiado.

#### `tests/test_calendar_sync/test_client.py`
- Mock de Google Calendar API: CRUD funciona.
- Error 429 → reintento con backoff.
- `eliminar_evento` con ID inexistente → `EventoNoEncontradoError`.
- `listar_proximos_eventos` retorna eventos ordenados por fecha.

---

## Criterios de Aceptación

- [ ] `build_event()` genera un dict válido para la Google Calendar API.
- [ ] `build_patch()` solo modifica los campos indicados en `EditInstruction`.
- [ ] Colores se asignan correctamente según `TipoServicio`.
- [ ] El conflict checker detecta eventos solapados con buffer de 30 min.
- [ ] `suggest_alternatives` genera exactamente 3 horarios alternativos.
- [ ] El cliente reintenta hasta 3 veces con backoff en errores transitorios.
- [ ] `listar_proximos_eventos` retorna los N próximos eventos ordenados por fecha.
- [ ] `buscar_eventos_por_cliente` encuentra eventos del cliente indicado.
- [ ] `format_event_list_item` genera texto con emoji de número, fecha, hora, color y tipo.

---

## Dependencias Nuevas

```
google-api-python-client>=2.100.0
google-auth>=2.23.0
pytz>=2024.1
```
