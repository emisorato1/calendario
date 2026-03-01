# Sprint 2 — Motor NLU (Groq Parser)

> **Duración estimada**: 2-3 sesiones de trabajo  
> **Objetivo**: El sistema puede interpretar mensajes de texto natural, extraer datos estructurados, identificar intenciones complejas (incluyendo edición y distintos tipos de consulta) y producir un `EditInstruction` cuando el usuario desea modificar un evento existente.  
> **Pre-requisito**: Sprint 1 completado.

---

## Entregables

### 1. `agents/groq_parser/schemas.py`

#### Enums

```python
class Intencion(str, Enum):
    agendar = "agendar"
    cancelar = "cancelar"
    editar = "editar"
    listar_pendientes = "listar_pendientes"
    listar_historial = "listar_historial"
    listar_dia = "listar_dia"
    listar_cliente = "listar_cliente"
    otro = "otro"

class TipoServicio(str, Enum):
    instalacion = "instalacion"
    revision = "revision"
    mantenimiento = "mantenimiento"
    presupuesto = "presupuesto"
    reparacion = "reparacion"
    otro = "otro"
```

#### `ParsedMessage` (Pydantic BaseModel)

Campos:
- `intencion: Intencion`
- `nombre_cliente: str | None`
- `tipo_servicio: TipoServicio | None`
- `fecha: date | None`
- `hora: time | None`
- `duracion_estimada_horas: float | None`
- `direccion: str | None`
- `telefono: str | None`
- `fecha_consulta: date | None` — Para intenciones `listar_dia`
- `cliente_consulta: str | None` — Para intenciones `listar_cliente`
- `urgente: bool = False` — Detectado cuando el usuario indica que el turno es urgente (ej: *"es urgente"*, *"para ya"*). Permite saltar el bloqueo de día lleno.

Validadores:
- `fecha` no puede ser en el pasado (si se proporciona). **Excepción**: si `urgente=True` y hay conflicto de horario, el orquestador permite igualmente el agendamiento pero advierte al usuario.
- `telefono` solo dígitos, 8-13 caracteres.
- `duracion_estimada_horas` se infiere del `tipo_servicio` si no viene explícita (usar `DURACIONES_SERVICIO` de `constants.py`).

#### `EditInstruction` (Pydantic BaseModel)

Para cuando el LLM interpreta una instrucción de edición en lenguaje natural:

```python
class EditInstruction(BaseModel):
    nueva_fecha: date | None = None
    nueva_hora: time | None = None
    nuevo_tipo_servicio: TipoServicio | None = None
    nueva_direccion: str | None = None
    nuevo_telefono: str | None = None
    nueva_duracion_horas: float | None = None
    # Al menos un campo debe estar presente → validador
```

Validador: debe tener al menos 1 campo no-None (si todos son None, el LLM no identificó nada).

---

### 2. `agents/groq_parser/prompts.py`

#### System Prompt Principal

```
Eres el asistente de agenda de un técnico instalador de cámaras y alarmas en Argentina (San Rafael, Mendoza).
Tu tarea es analizar mensajes de texto y devolver SIEMPRE un JSON válido con la estructura indicada.
Fecha y hora actual: {fecha_actual} {hora_actual} (zona horaria: America/Argentina/Buenos_Aires).
Servicios disponibles: instalacion, revision, mantenimiento, presupuesto, reparacion, otro.
Intenciones posibles: agendar, cancelar, editar, listar_pendientes, listar_historial, listar_dia, listar_cliente, otro.
REGLAS: No inventes datos. Si un campo no está en el mensaje, ponlo en null. Resuelve fechas relativas (hoy, mañana, el lunes) usando la fecha actual.
```

#### System Prompt para Edición

Prompt separado para el paso 2 del flujo de edición, donde el usuario ya seleccionó un evento y escribe la instrucción de cambio:

```
Eres el asistente de agenda. El usuario quiere modificar un evento existente.
Evento actual: {evento_actual_json}
Instrucción del usuario: {instruccion}
Devuelve un JSON con SOLO los campos que deben cambiar. Usa null para los que NO cambian.
Campos posibles: nueva_fecha, nueva_hora, nuevo_tipo_servicio, nueva_direccion, nuevo_telefono, nueva_duracion_horas.
```

#### User Prompt Templates

- `build_parse_prompt(mensaje: str, fecha_actual: str) -> str`
- `build_edit_prompt(evento_actual: dict, instruccion: str) -> str`

---

### 3. `agents/groq_parser/client.py`

- Wrapper sobre `groq` SDK Python.
- Timeout de 10 segundos por request.
- Reintentos con `tenacity`: 3 intentos, backoff exponencial (1s, 2s, 4s).
- Excepciones a reintentar: `APITimeoutError`, `APIConnectionError`, `RateLimitError`.
- Fallback automático al modelo secundario si el primario falla 3 veces.
- Logging de cada llamada: modelo usado, tokens consumidos, latencia en ms.

**Firma del método principal:**
```python
async def call(
    self,
    system_prompt: str,
    user_prompt: str,
    response_format: type[BaseModel]
) -> dict
```

---

### 4. `agents/groq_parser/parser.py`

Dos funciones principales:

```python
async def parse_message(text: str, fecha_actual: date) -> ParsedMessage:
    """Pipeline: componer prompt → llamar LLM → parsear JSON → validar schema."""
    # Si Pydantic falla, reintenta hasta 2 veces con mensaje de error en el prompt.

async def parse_edit_instruction(
    instruccion: str,
    evento_actual: dict,
    fecha_actual: date
) -> EditInstruction:
    """Pipeline para interpretar una instrucción de edición sobre un evento existente."""
```

---

### 5. Tests

#### `tests/test_groq_parser/test_schemas.py`
- `ParsedMessage` válido se crea correctamente.
- Fecha en el pasado → lanza `ValidationError`.
- Teléfono inválido → lanza `ValidationError`.
- `duracion_estimada_horas` se infiere si es None.
- `EditInstruction` sin ningún campo → lanza `ValidationError`.

#### `tests/test_groq_parser/test_parser.py`
- Mock Groq devuelve JSON válido → `ParsedMessage` correcto.
- Mock Groq devuelve JSON inválido 2 veces → lanza `GroqParsingError`.
- `parse_edit_instruction` extrae correctamente fecha/hora/tipo de instrucciones en lenguaje natural.

#### `tests/test_groq_parser/test_client.py`
- Timeout → reintento con backoff → fallback al modelo secundario.
- Rate limit → reintento correcto.
- 3 fallos consecutivos → lanza `GroqTimeoutError`.

---

## Casos de Test Clave

| Mensaje Input | Intención Esperada | Campos Esperados |
|---|---|---|
| `"Agendame para mañana a las 10 instalación en lo de García"` | `agendar` | `nombre: García, tipo: instalacion, hora: 10:00, duracion: 3.0` |
| `"Qué tengo para el lunes?"` | `listar_dia` | `fecha_consulta: próximo lunes` |
| `"Cancelá lo de Pérez"` | `cancelar` | `nombre_cliente: Pérez` |
| `"Editá el turno de López"` | `editar` | `nombre_cliente: López` |
| `"Qué hice la semana pasada?"` | `listar_historial` | — |
| `"¿Cuándo tengo que ir a lo de Juan?"` | `listar_cliente` | `cliente_consulta: Juan` |
| `"Hola"` | `otro` | — |
| Instrucción de edición: `"Pasalo para el viernes a las 16"` | `EditInstruction` | `nueva_fecha: viernes, nueva_hora: 16:00` |
| Instrucción de edición: `"Cambiá el servicio a instalación de cámaras"` | `EditInstruction` | `nuevo_tipo_servicio: instalacion` |

---

## Criterios de Aceptación

- [ ] `ParsedMessage` detecta correctamente las 8 intenciones.
- [ ] Fechas relativas ("mañana", "el lunes", "el viernes que viene") se resuelven correctamente.
- [ ] JSON inválido del LLM → se reintenta hasta 2 veces → si sigue fallando, `GroqParsingError`.
- [ ] Timeout de Groq → reintento con backoff → fallback → `GroqTimeoutError`.
- [ ] `EditInstruction` sin campos → `ValidationError`.
- [ ] `parse_edit_instruction` identifica correctamente el campo modificado en instrucciones en lenguaje natural.

---

## Dependencias Nuevas

```
groq>=0.9.0
tenacity>=8.2.0
```
