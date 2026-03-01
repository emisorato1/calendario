# 🤖 Telegram Bot — Interfaz de Usuario

Módulo encargado de la comunicación bidireccional con los usuarios a través de
Telegram. Gestiona menús de botones, handlers de comandos, conversaciones
interactivas y la recepción de archivos multimedia (fotos).

## Propósito

Proveer una interfaz intuitiva y accesible para que los técnicos y
administradores gestionen sus servicios sin necesidad de aplicaciones web
o escritorio. Telegram es universal, liviano y funciona en cualquier dispositivo.

## Casos de Uso

- **Menú principal con botones inline**: Presentar las acciones disponibles
  según el rol del usuario.
- **Handlers de comandos**: `/start`, `/menu`, `/help`, `/cancel`.
- **Conversaciones multi-paso**: Flujos guiados donde el bot pregunta y el
  usuario responde (ConversationHandler).
- **Recepción de fotos**: Para adjuntar al cierre de un servicio.
- **Mensajes en lenguaje natural**: Capturar texto libre y delegarlo al parser LLM.
- **Respuestas formateadas**: Mostrar eventos y contactos de forma prolija y legible.

## Tecnología

- **Librería**: `python-telegram-bot` v20+ (asyncio nativo).
- **Patrón**: `ConversationHandler` para flujos multi-paso.
- **Polling**: Se usa polling en lugar de webhooks para simplificar deploy
  en servidores de recursos limitados.

## Patrones

- Cada acción del menú tiene su propio handler module.
- Los handlers son **thin** (delgados): solo traducen la interacción de
  Telegram a llamadas al Orquestador.
- Validación de permisos mediante decoradores o middleware.
- Manejo de timeouts para conversaciones abandonadas.

## Anti-patrones a Evitar

- ❌ Poner lógica de negocio directamente en los handlers.
- ❌ Acceder a la BD o Calendar desde los handlers.
- ❌ Hardcodear textos de respuesta (usar constantes/templates).
- ❌ Ignorar excepciones de la API de Telegram.

## Referencias

- [Estructura de Handlers](references/handler-structure.md)
- [Menú y Botones Inline](references/menu-buttons.md)
- [ConversationHandler Patterns](references/conversation-patterns.md)
- [Formato de Respuestas](references/response-formatting.md)
