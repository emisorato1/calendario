# 🧠 LLM Parser — Comprensión de Lenguaje Natural

Módulo encargado de interpretar mensajes en lenguaje natural del usuario y
extraer datos estructurados (intenciones, entidades, parámetros) usando un
modelo de lenguaje grande (LLM).

## Propósito

Permitir que el usuario interactúe con el bot usando lenguaje natural sin
necesidad de completar formularios rígidos. El parser transforma texto libre
en acciones y datos estructurados que el orquestador puede ejecutar.

## Casos de Uso

- **Detección de intención**: Identificar qué acción quiere realizar el
  usuario (crear, editar, eliminar, ver, terminar evento, ver contactos).
- **Extracción de entidades**: Extraer nombre del cliente, teléfono,
  dirección, tipo de servicio, fecha/hora, notas.
- **Interpretación de ediciones**: Entender qué campos del evento modificar.
- **Cierre de servicio**: Extraer trabajo realizado, monto, notas de cierre.
- **Resolución de fechas relativas**: "mañana", "el viernes", "la semana que
  viene", "pasado mañana a las 10".
- **Fallback**: Si no se puede interpretar, devolver una pregunta de clarificación.

## Tecnología

- **Primario**: Groq API (Llama 3.3 70B).
- **Fallback**: Gemini API o OpenAI API.
- **Validación**: Pydantic v2 para validar la respuesta del LLM.
- **Prompts**: Prompt engineering con contexto de negocio (servicios técnicos).

## Patrones

- **Structured Output**: El LLM devuelve JSON que se valida con Pydantic.
- **Retry con Backoff**: Reintentos exponenciales ante errores transitorios.
- **Fallback Chain**: Groq → Gemini → OpenAI.
- **Prompt Templates**: Templates parametrizados para cada tipo de acción.
- **Few-shot Examples**: Incluir ejemplos en el prompt para mejorar precisión.

## Anti-patrones a Evitar

- ❌ Confiar ciegamente en la salida del LLM sin validación.
- ❌ Usar el LLM para lógica que se puede resolver con reglas simples.
- ❌ Enviar datos sensibles al LLM (tokens, contraseñas).
- ❌ No manejar el caso de respuesta inválida o timeout del LLM.
- ❌ Prompts excesivamente largos que consumen tokens innecesariamente.

## Referencias

- [Prompts y Templates](references/prompts.md)
- [Schemas Pydantic](references/schemas.md)
- [Fallback Strategy](references/fallback-strategy.md)
- [Resolución de Fechas](references/date-resolution.md)
