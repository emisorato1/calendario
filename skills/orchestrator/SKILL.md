# 🎯 Orquestador — Lógica de Negocio Central

Módulo central que coordina la interacción entre todos los componentes del
sistema: Telegram Bot, LLM Parser, SQLite Database y Google Calendar.

## Propósito

El Orquestador es el **cerebro del sistema**. Recibe las solicitudes de los
handlers de Telegram, coordina con el LLM para interpretar mensajes, ejecuta
las operaciones necesarias en la BD y el calendario, y devuelve resultados
formateados al usuario.

## Casos de Uso

- **Crear evento**: Parser → validar datos → crear/buscar cliente → crear
  evento en SQLite → crear evento en Calendar → confirmar.
- **Editar evento**: Parser → identificar evento → aplicar cambios en BD
  → sincronizar Calendar → confirmar.
- **Eliminar evento**: Verificar permisos → eliminar de BD → eliminar de
  Calendar → confirmar.
- **Completar evento**: Parser cierre → actualizar BD → actualizar Calendar
  (color verde + descripción) → confirmar.
- **Resolver conflictos**: Verificar disponibilidad antes de agendar.
- **Flujo natural sin botones**: Detectar intención → delegar al caso de uso correspondiente.

## Tecnología

- Python puro con `asyncio`.
- Inyección de dependencias: recibe repositorio, calendar client y parser.

## Patrones

- **Mediator Pattern**: El orquestador media entre todos los módulos.
- **Dependency Injection**: Los componentes se inyectan en el constructor.
- **Result Pattern**: Los métodos devuelven objetos `Result` que pueden
  contener éxito, error o pregunta de clarificación.
- **Transaction Coordination**: Si falla Calendar, se revierte la BD.

## Anti-patrones a Evitar

- ❌ Que los handlers de Telegram accedan directamente a la BD o Calendar.
- ❌ Que el orquestador conozca detalles de la API de Telegram.
- ❌ Operaciones parciales sin rollback (ej: se creó en BD pero falló en Calendar).
- ❌ Lógica de presentación (formateo de mensajes) en el orquestador.
- ❌ Estado mutable compartido entre operaciones concurrentes.

## Referencias

- [Flujo de Creación de Evento](references/create-event-flow.md)
- [Manejo de Errores y Result Pattern](references/error-handling.md)
- [Coordinación BD-Calendar](references/sync-coordination.md)
