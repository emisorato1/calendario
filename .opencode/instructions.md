# Agente Calendario — Guía Fundacional

## Descripción del Proyecto

Bot de Telegram con IA para la gestión integral de servicios técnicos
(cámaras de seguridad, alarmas, porteros eléctricos, software).
Sincroniza una base de datos SQLite con Google Calendar.

## Documentación

- **[Documento Principal](../idea_general_proyecto.md)**: Visión, arquitectura, casos de uso, modelo de datos.
- **[Specs](../specs/README.md)**: Especificaciones técnicas organizadas por sprint.
- **[Skills](../skills/)**: Módulos de conocimiento técnico con referencias.

## Arquitectura

```
Telegram → Bot Handlers → Orquestador → {LLM Parser, SQLite, Google Calendar}
```

## Stack

- Python 3.11+ | python-telegram-bot v20+ | Pydantic v2
- SQLite (WAL) + aiosqlite | Groq/Gemini/OpenAI | Google Calendar API v3

## Principios

- **KISS**: SQLite, polling (no webhooks), sin servicios extra.
- **SOLID**: Cada módulo = una responsabilidad.
- **Fail-Safe**: Fallback LLM, rollback BD↔Calendar, reintentos con backoff.

## Sprints

| Sprint | Entregable                            |
|--------|---------------------------------------|
| 1      | Config, DB, modelos, repositorio      |
| 2      | Parser LLM (Groq) + fallback         |
| 3      | Google Calendar CRUD                  |
| 4      | Bot Telegram: menú, handlers, flujos  |
| 5      | Orquestador + integración completa    |
