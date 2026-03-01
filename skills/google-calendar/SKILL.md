# 📅 Google Calendar — Sincronización de Agenda

Módulo encargado de la integración con Google Calendar API v3 para crear,
leer, actualizar y eliminar eventos, manteniendo la sincronización con
la base de datos local.

## Propósito

Google Calendar actúa como la **vista compartida** de la agenda. Todos los
técnicos y administradores pueden ver los eventos desde la app de Google
Calendar en sus dispositivos, mientras que la base de datos SQLite es la
**fuente de verdad** del sistema.

## Casos de Uso

- **Crear evento**: Con título, ubicación, descripción formateada y color
  según tipo de servicio.
- **Actualizar evento**: Cambiar fecha, hora, descripción, ubicación o color.
- **Eliminar evento**: Remover del calendario.
- **Completar evento**: Cambiar color a verde y actualizar descripción con
  datos de cierre (trabajo realizado, monto, notas).
- **Listar eventos**: Consultar eventos del calendario para verificar
  conflictos de horario.

## Tecnología

- **Google Calendar API v3** con `google-api-python-client`.
- **Autenticación**: Service Account con delegación de dominio o acceso
  directo al calendario.
- **Credenciales**: `credentials/service_account.json` (no versionado).

## Patrones

- **Wrapper Pattern**: Encapsular la API de Google en una interfaz simple.
- **Retry con Backoff**: Para errores transitorios de red o rate limiting.
- **Color Mapping**: Mapeo centralizado tipo_servicio → color_id.
- **Template de Descripción**: Formato consistente para todas las descripciones.

## Anti-patrones a Evitar

- ❌ Exponer la API de Google directamente a los handlers.
- ❌ Ignorar errores de la API (rate limit, auth, network).
- ❌ No validar que el evento existe antes de actualizarlo.
- ❌ Hardcodear el Calendar ID (usar `.env`).
- ❌ Crear eventos sin verificar conflictos de horario.

## Referencias

- [CRUD de Eventos](references/event-crud.md)
- [Colores y Mapping](references/color-mapping.md)
- [Formato de Descripción](references/description-format.md)
