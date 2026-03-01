# Sprint 5 — Cancelación Interactiva, Edición Inteligente y Motor de Consultas

> **Duración estimada**: 3-4 sesiones de trabajo  
> **Objetivo**: Completar los flujos interactivos de cancelación y edición iniciados en el Sprint 4, e implementar el motor de consultas con los 4 tipos de filtros de listado.  
> **Pre-requisito**: Sprint 4 completado.

---

## Entregables

### 1. `core/orchestrator.py` — Flujos de Cancelación y Edición

Ampliación del `Orchestrator` con los métodos que completan los flujos iniciados en Sprint 4.

#### Flujo de Cancelación

```python
async def confirm_cancel(self, event_id: str) -> OrchestratorResponse:
    """
    Elimina el evento seleccionado del Calendar y actualiza su estado
    en el historial de DB a 'cancelado'.
    Retorna mensaje de confirmación o error.
    """
```

**Comportamiento completo del flujo:**
1. Usuario presiona `🚫 Cancelar Evento` (o escribe con intención `cancelar`).
2. `get_upcoming_events_for_selection()` → lista de próximos eventos formateados.
3. Usuario selecciona el número del evento.
4. Bot muestra confirmación específica: *"¿Eliminás Revisión — García, Juan del Lun 02/03?"*
   - Botones: `[✅ Sí, eliminar] [❌ No, volver]`
5. Si confirma → `confirm_cancel(event_id)` → evento eliminado del Calendar + historial actualizado.
6. Si cancela → volver a `IDLE` sin cambios.

---

#### Flujo de Edición

```python
async def parse_and_preview_edit(
    self,
    instruccion: str,
    evento_actual: dict,
) -> OrchestratorResponse:
    """
    Paso 2 del flujo de edición: el usuario ya seleccionó un evento
    y escribió su instrucción en lenguaje natural.
    
    1. Llama a groq_parser.parse_edit_instruction(instruccion, evento_actual).
    2. Genera el dict de PATCH con calendar_sync.build_patch().
    3. Construye y retorna el resumen de los cambios + teclado de confirmación.
    """

async def confirm_edit(
    self,
    event_id: str,
    patch: dict,
    servicio_id: int | None = None,
) -> OrchestratorResponse:
    """
    Post-confirmación del usuario en el flujo de edición:
    1. calendar_sync.actualizar_evento(event_id, patch).
    2. Si cambió el tipo de servicio, actualizar registro en historial DB.
    3. Retornar confirmación con link al evento actualizado.
    """
```

**Comportamiento completo del flujo:**
1. Usuario presiona `✏️ Editar Evento` (o escribe con intención `editar`).
2. `get_upcoming_events_for_selection()` → lista de próximos eventos.
3. Usuario selecciona el número del evento.
4. Bot responde: *"¿Qué querés cambiar? Escribilo en lenguaje natural."*
5. Usuario escribe instrucción (ej: *"Pasalo para el viernes a las 16"*).
6. `parse_and_preview_edit()` → LLM interpreta → muestra resumen de cambios:
   ```
   ✏️ *Cambios propuestos:*
   
   📅 Fecha: Lun 02/03 → Vie 06/03
   🕐 Hora: 09:00 → 16:00
   
   ¿Aplicar cambios?
   [✅ Aplicar cambios] [❌ Cancelar]
   ```
7. Si confirma → `confirm_edit()` → PATCH en Calendar.
8. Si cancela → volver a `IDLE` sin cambios.

---

### 2. `core/orchestrator.py` — Motor de Consultas

```python
async def listar_pendientes(self) -> str:
    """
    Todos los eventos futuros desde ahora hasta 30 días adelante.
    Formato estandarizado de lista.
    """

async def listar_historial(self, dias: int = 30) -> str:
    """
    Eventos pasados de los últimos N días.
    Formato estandarizado de lista.
    """

async def listar_por_dia(self, fecha: date) -> str:
    """
    Todos los eventos de una fecha específica.
    Si no hay eventos: mensaje apropiado ("No tenés nada para ese día.").
    """

async def listar_por_cliente(self, nombre_cliente: str) -> str:
    """
    Busca en el historial de DB todos los servicios del cliente (fuzzy match),
    luego corrobora con Calendar para obtener detalles actualizados.
    Muestra pendientes primero, luego historial.
    """
```

**Formato de listado estándar:**
```
📅 *Eventos pendientes (5):*

📌 Lun 02/03 | 09:00 - 10:00 | 🟡 Revisión — García, Juan
📌 Mar 03/03 | 10:00 - 13:00 | 🔵 Instalación — López, Pedro
📌 Vie 06/03 | 14:00 - 16:00 | 🟠 Mantenimiento — Martínez, Carlos
```

**Listado por cliente (formato extendido):**
```
👤 *Turnos de García, Juan:*

Próximos:
📌 Lun 02/03 | 09:00 - 10:00 | 🟡 Revisión

Historial:
✅ Lun 12/01 | 10:00 - 13:00 | 🔵 Instalación (realizado)
```

---

### 3. `core/work_schedule.py` — Motor de Horario Laboral

Módulo dedicado a la lógica de horario laboral.

```python
def get_day_schedule(fecha: date, settings: Settings) -> dict | None:
    """
    Retorna el horario laboral del día.
    - Lunes-Viernes (weekday 0-4): usa WORK_DAYS_WEEKDAY_START/END.
    - Sábado (weekday 5): usa WORK_DAYS_SATURDAY_START/END.
    - Domingo (weekday 6): retorna None (sin actividad).
    Retorna: {'start': time, 'end': time, 'total_hours': float} o None.
    """

def get_available_slots(
    fecha: date,
    duracion_horas: float,
    eventos_del_dia: list[dict],
    settings: Settings,
) -> list[tuple[time, time]]:
    """
    Retorna lista de RANGOS horarios disponibles como tuplas (inicio, fin).
    Cada franja cubre exactamente `duracion_horas` horas.
    Algoritmo:
    1. Obtener rango laboral del día.
    2. Iterar por franjas de TIME_SLOT_INTERVAL_MINUTES desde start hasta end.
    3. Para cada franja calcular (inicio, fin = inicio + duracion_horas).
    4. Verificar que:
       a. `fin` no supera el cierre del día.
       b. El rango no se solapa con eventos existentes (buffer 30 min).
    5. Retornar lista de tuplas (inicio, fin) disponibles.
    
    Ejemplo (lunes 15:00-21:00, duración 2h, sin eventos):
    [(15:00, 17:00), (16:00, 18:00), (17:00, 19:00), (18:00, 20:00), (19:00, 21:00)]
    """

def calculate_free_hours(
    fecha: date,
    eventos_del_dia: list[dict],
    settings: Settings,
) -> float:
    """
    Calcula las horas laborales libres en un día.
    total_hours_del_dia - sum(duración de cada evento agendado).
    """

def is_day_fully_booked(
    fecha: date,
    duracion_horas: float,
    eventos_del_dia: list[dict],
    settings: Settings,
) -> bool:
    """
    Retorna True si NO existe ninguna franja (inicio, fin) disponible
    para un evento de exactamente `duracion_horas` horas.
    Equivalente a: len(get_available_slots(...)) == 0.
    """
```

#### Flujo cuando el día está lleno (creación)

Cuando `is_day_fully_booked()` = True y el usuario **no marcó urgencia**, el bot responde:

```
⚠️ *El martes 03/03 está completo.*
Ya no quedan franjas disponibles para ese día.

🗓️ Te recomiendo elegir otro día.
Si el turno es urgente, podés agendarlo igual.

[📅 Elegir otro día] [🚨 Es urgente — agendar igual]
```

- Si elige `📅 Elegir otro día`: vuelve a `build_date_suggestion_keyboard()` y el ciclo reinicia.
- Si elige `🚨 Es urgente — agendar igual`: se setea `context_data['urgente'] = True` y se
  vuelve a `build_time_slot_keyboard()` mostrando solo el botón `¿Otro horario?`
  (el usuario debe escribir la hora manualmente, ya que no hay franjas libres prearmadas).

#### Uso en listados

Cuando `listar_por_dia()` o `listar_pendientes()` formatean la agenda de un día,
si el día está **100% ocupado** (`is_day_fully_booked()` = True), el bot agrega:

```
📅 *Martes 03/03/2026*
📌 16:00 - 17:00 | 🟡 Revisión — García, Juan
📌 18:00 - 20:00 | 🔵 Instalación — López, Pedro

⚠️ *Día completo* — No quedan franjas disponibles.
```

---

### 4. `agents/telegram_listener/handler.py` — Flujos Interactivos Completos

Implementación de los handlers para los estados definidos en Sprint 4:

#### Handler: `AWAITING_CREATION_INPUT`

```python
async def handle_creation_input(update, context):
    """
    Recibe el texto libre con la descripción del turno.
    Llama orchestrator.start_creation_flow(texto_parseado).
    Muestra resumen del evento con botones [✅ Confirmar] [❌ Cancelar].
    Pasa a estado AWAITING_CONFIRMATION.
    """
```

#### Handler: `AWAITING_CANCEL_SELECTION`

```python
async def handle_cancel_selection(update, context):
    """
    Recibe el número de evento seleccionado.
    Recupera el evento del context.user_data.
    Muestra mensaje de confirmación específico con botones [✅ Sí, eliminar] [❌ No, volver].
    Pasa a estado AWAITING_CANCEL_CONFIRM.
    """
```

#### Handler: `AWAITING_CANCEL_CONFIRM`

```python
async def handle_cancel_confirm(update, context):
    """
    Callback confirm → llama orchestrator.confirm_cancel(event_id).
    Callback cancel  → mensaje "Cancelación abortada." → IDLE.
    """
```

#### Handler: `AWAITING_EDIT_SELECTION`

```python
async def handle_edit_selection(update, context):
    """
    Recibe el número de evento seleccionado.
    Guarda el evento en context.user_data['evento_a_editar'].
    Responde: "¿Qué querés cambiar? Escribilo en lenguaje natural."
    Pasa a estado AWAITING_EDIT_INSTRUCTION.
    """
```

#### Handler: `AWAITING_EDIT_INSTRUCTION`

```python
async def handle_edit_instruction(update, context):
    """
    Recibe el texto libre con la instrucción de edición.
    Llama orchestrator.parse_and_preview_edit(instruccion, evento_actual).
    Muestra resumen de cambios con botones [✅ Aplicar] [❌ Cancelar].
    Pasa a estado AWAITING_EDIT_CONFIRM.
    """
```

#### Handler: `AWAITING_EDIT_CONFIRM`

```python
async def handle_edit_confirm(update, context):
    """
    Callback confirm → llama orchestrator.confirm_edit(event_id, patch).
    Callback cancel  → mensaje "Edición cancelada." → IDLE.
    """
```

---

### 4. `agents/telegram_listener/handler.py` — Submenú de Listados

Cuando el usuario presiona `📋 Listar Eventos` o escribe con intención de listar,
el bot presenta un submenú inline:

```
¿Qué querés ver?

[📌 Próximos eventos]  [📜 Historial]
[📅 Un día específico] [👤 Por cliente]
```

- `📌 Próximos eventos` → `orchestrator.listar_pendientes()`
- `📜 Historial` → `orchestrator.listar_historial()`
- `📅 Un día específico` → Bot pide la fecha: *"¿Qué día? (ej: lunes, 05/03, mañana)"* → `orchestrator.listar_por_dia(fecha)`
- `👤 Por cliente` → Bot pide el nombre: *"¿De qué cliente?"* → `orchestrator.listar_por_cliente(nombre)`

---

### 5. Tests

#### `tests/test_orchestrator.py` — Flujos Interactivos

- `confirm_cancel` → evento eliminado de Calendar (mock) + estado DB actualizado a 'cancelado'.
- `confirm_cancel` con event_id inválido → `EventoNoEncontradoError` manejado correctamente.
- `parse_and_preview_edit` con *"pasalo para el viernes a las 16"* → preview con fecha y hora correctas.
- `parse_and_preview_edit` con *"cambiá el servicio a instalación"* → preview con nuevo tipo y nuevo color.
- `confirm_edit` → PATCH en Calendar (mock) + DB actualizado.

#### `tests/test_orchestrator.py` — Motor de Consultas

- `listar_pendientes` → lista formateada con eventos futuros.
- `listar_pendientes` sin eventos → mensaje "No tenés eventos pendientes."
- `listar_historial` → lista formateada con eventos pasados.
- `listar_por_dia` con día con eventos → lista del día.
- `listar_por_dia` con día vacío → mensaje "No tenés nada para ese día."
- `listar_por_cliente` encuentra cliente con fuzzy match y returna pendientes + historial.
- `listar_por_cliente` con cliente no encontrado → mensaje apropiado.

#### `tests/test_telegram_listener/test_handler.py` — Flujos Interactivos

- Presionar `📅 Crear Turno` → bot muestra cartel de ayuda, estado pasa a `AWAITING_CREATION_INPUT`.
- Input de creación en `AWAITING_CREATION_INPUT` → bot procesa y muestra resumen, estado pasa a `AWAITING_CONFIRMATION`.
- Selección de evento válida en `AWAITING_CANCEL_SELECTION` → avanza a `AWAITING_CANCEL_CONFIRM`.
- Selección de número fuera de rango → mensaje de error, mantiene estado.
- `confirm_cancel` exitoso → mensaje de confirmación, vuelve a `IDLE`.
- `AWAITING_EDIT_INSTRUCTION` recibe instrucción → llama `parse_and_preview_edit`.
- `confirm_edit` exitoso → mensaje de confirmación con link, vuelve a `IDLE`.
- Submenú `📋 Listar Eventos` muestra las 4 opciones.

---

## Criterios de Aceptación

- [ ] Cancelación interactiva: nunca se elimina un evento sin mostrar la lista y pedir confirmación.
- [ ] Edición inteligente: el LLM identifica correctamente el campo modificado en instrucción NLU.
- [ ] Edición inteligente: si cambia el tipo de servicio, el color del evento se actualiza.
- [ ] `listar_pendientes` muestra eventos futuros en formato correcto (Día, Hora, Tipo, Cliente).
- [ ] `listar_historial` muestra eventos pasados correctamente.
- [ ] `listar_por_dia` funciona con fechas relativas ("el lunes", "mañana") y absolutas ("05/03").
- [ ] `listar_por_cliente` usa fuzzy match y devuelve pendientes + historial del cliente.
- [ ] Selección de número fuera de rango en cancelar/editar no rompe el flujo.
- [ ] La cancelación abortada con `❌` no elimina ningún evento.
- [ ] La edición abortada con `❌` no modifica ningún evento.
- [ ] `get_available_slots()` excluye correctamente franjas ocupadas y las que no caben antes del cierre.
- [ ] `is_day_fully_booked()` retorna True cuando no hay ninguna franja disponible.
- [ ] El listado de un día lleno incluye el aviso `⚠️ Día completo`.
- [ ] Domingos: `get_day_schedule()` retorna None y el bot bloquea el agendamiento.
