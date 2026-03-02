# Sprint 2 — Parser LLM

## Descripción

Implementar el módulo de comprensión de lenguaje natural que interpreta
mensajes del usuario, extrae intenciones y entidades (cliente, servicio,
fecha, hora, dirección) y devuelve datos estructurados validados con Pydantic.

## Objetivos

- [ ] Implementar cliente Groq con retry y backoff exponencial.
- [ ] Implementar cadena de fallback LLM: Groq → Gemini → OpenAI.
- [ ] Crear prompts templates para cada tipo de acción.
- [ ] Implementar schemas Pydantic para validar respuestas del LLM.
- [ ] Implementar detección de intención general (sin botones).
- [ ] Implementar parsing de creación de evento con extracción de entidades.
- [ ] Implementar parsing de edición y cierre de servicio.
- [ ] Manejar resolución de fechas relativas ("mañana", "el viernes").
- [ ] Garantizar que `tipo_servicio` NUNCA sea null (default "otro", validador).
- [ ] Implementar campo `prioridad` (alta/normal) en `ParsedEvent`.
- [ ] Implementar regla: NUNCA asumir "hoy" si no hay día explícito.
- [ ] Implementar regla: si faltan fecha y hora, preguntar SOLO por la fecha.

## Requisitos Técnicos

| Requisito        | Detalle                                              |
| ---------------- | ---------------------------------------------------- |
| LLM primario     | Groq SDK (`groq` package)                           |
| LLM fallback     | Gemini / OpenAI (opcionales, según config)           |
| Temperatura      | 0.1 (respuestas consistentes)                        |
| Max tokens       | 512 (configurable en `.env`)                         |
| Timeout          | 10 segundos por request                              |
| Reintentos       | 2 por proveedor, backoff exponencial                 |
| Formato          | JSON structured output validado con Pydantic         |

## Pasos de Implementación

### 1. Schemas (`src/llm/schemas.py`)

- `Intent` (Enum): crear_evento, editar_evento, ver_eventos, eliminar_evento,
  terminar_evento, ver_contactos, editar_contacto, saludo, ayuda, desconocido.
- `TipoServicio` (Enum): reutilizar de `db.models`.
- `Prioridad` (Enum): normal, alta.
- `ParsedEvent`: intent, cliente, teléfono, dirección, tipo_servicio
  (**default "otro", NUNCA null**, validador `tipo_never_null`),
  fecha, hora, duración, notas, prioridad, missing_fields,
  clarification_question, confidence.
  Properties: `needs_clarification`, `is_complete`, `has_date_but_no_time`,
  `is_high_priority`.
- `ParsedEdit`: intent, changes dict, clarification_question.
- `ParsedClosure`: intent, trabajo_realizado, monto, notas_cierre,
  missing_fields, clarification_question.
- `IntentDetection`: intent, confidence, extracted_data.

### 2. Prompts (`src/llm/prompts.py`)

- `SYSTEM_PROMPT`: Contexto de negocio (empresa de servicios técnicos),
  tipos de servicio válidos, zona horaria, fecha actual.
  **Reglas obligatorias**: nunca asumir "hoy", tipo siempre obligatorio,
  preguntas secuenciales (fecha antes que hora), detección de prioridad.
- `CREATE_EVENT_PROMPT`: Template para extraer datos de evento nuevo.
  Incluye campo `prioridad` y reglas de fecha/hora.
- `EDIT_EVENT_PROMPT`: Template para identificar cambios.
- `CLOSURE_PROMPT`: Template para datos de cierre de servicio.
- `INTENT_DETECTION_PROMPT`: Template para detección de intención general.
- Incluir **few-shot examples** en cada prompt (con casos de datos completos,
  falta de fecha, falta de hora, y prioridad alta).

### 3. Cliente LLM (`src/llm/client.py`)

- `LLMProvider` dataclass: name, client, model, timeout, max_retries.
- `LLMChain`: Cadena de proveedores con fallback automático.
- Método `complete(messages) → str`: Intenta cada proveedor en orden.
- Backoff exponencial entre reintentos: 1s, 2s, 4s.
- Logging de qué proveedor respondió y cuántos intentos.

### 4. Parser (`src/llm/parser.py`)

- `LLMParser`: Clase principal que usa `LLMChain` y `prompts`.
- `detect_intent(text) → IntentDetection`
- `parse_create_event(text) → ParsedEvent`
- `parse_edit_event(text, current_event) → ParsedEdit`
- `parse_closure(text) → ParsedClosure`
- Validación de respuesta JSON con Pydantic (retry si es inválido).
- Inyección de fecha/día actual en cada prompt.

### 5. Respuesta de Fallback Estática

Si todos los LLM fallan:
```
"⚠️ No pude procesar tu mensaje en este momento.
Intentá de nuevo en unos segundos o usá los botones del menú (/menu)."
```

### 6. Tests

- `tests/unit/test_schemas.py`: Validación de cada schema con datos válidos e inválidos.
- `tests/unit/test_prompts.py`: Verificar que los templates se formatean correctamente.
- `tests/unit/test_parser.py`: Mock del LLM, verificar extracción de entidades.
- `tests/unit/test_client.py`: Mock de proveedores, verificar fallback chain.

## Criterios de Aceptación

- [ ] El parser detecta correctamente al menos 8 de 10 intenciones de ejemplo.
- [ ] Extrae nombre, teléfono, tipo de servicio, fecha y hora de mensajes naturales.
- [ ] Resuelve "mañana a las 10" correctamente a una fecha/hora concreta.
- [ ] Si falta info obligatoria, devuelve pregunta de clarificación.
- [ ] Si Groq falla, el fallback a otro LLM es transparente.
- [ ] Si todos los LLM fallan, responde con mensaje de fallback estático.
- [ ] `tipo_servicio` NUNCA es null. Si no se puede determinar, default "otro".
- [ ] El campo `prioridad` se extrae correctamente ("urgente" → alta, default normal).
- [ ] Si no hay día explícito en el mensaje, `fecha` es null (NUNCA asume "hoy").
- [ ] Si faltan fecha y hora, `clarification_question` pregunta SOLO por la fecha.
- [ ] Si el mensaje tiene todos los datos, `missing_fields=[]` y `clarification_question=null`.
- [ ] Todos los tests pasan.

## Skills Referenciadas

- [LLM Parser](../../skills/llm-parser/SKILL.md)
  - [Prompts y Templates](../../skills/llm-parser/references/prompts.md)
  - [Schemas Pydantic](../../skills/llm-parser/references/schemas.md)
  - [Fallback Strategy](../../skills/llm-parser/references/fallback-strategy.md)
  - [Resolución de Fechas](../../skills/llm-parser/references/date-resolution.md)
