# Agente Calendario — Guía Fundacional

> **Versión**: 2.0  
> **Contexto**: Asistente virtual por Telegram para un técnico instalador de cámaras y alarmas. Gestiona agenda en Google Calendar con interfaz híbrida (botones + lenguaje natural) y CRM local en SQLite.

---

## 🎯 Visión del Sistema

### Propósito
Automatizar la gestión de agenda y clientes de un técnico instalador mediante un agente de IA accesible por Telegram. El agente interpreta mensajes de texto natural Y responde a botones de menú interactivo. Puede crear, editar, cancelar y consultar eventos de forma inteligente.

### Alcance del Sistema
- **Entrada**: Mensajes de texto en Telegram (botones de menú o lenguaje natural libre).
- **Procesamiento**: LLM vía Groq API para NLU (Natural Language Understanding).
- **Persistencia**: SQLite para CRM local (clientes + historial de servicios).
- **Integración**: Google Calendar API para gestión de agenda.
- **Salida**: Confirmaciones, listados formateados y menú interactivo por Telegram.

---

## 🏗️ Arquitectura de Módulos

```
agents/
├── telegram_listener/      # Interfaz Telegram (handlers, teclados, estados)
├── groq_parser/            # Motor NLU (intención + extracción + edición)
├── db_manager/             # CRM SQLite (clientes + historial)
└── calendar_sync/          # Google Calendar (CRUD de eventos + búsquedas)

core/
├── orchestrator.py         # Orquestador central (conecta todos los módulos)
├── work_schedule.py        # Motor de horario laboral (capacidad, franjas disponibles)
├── logger.py               # Logging estructurado
└── exceptions.py           # Excepciones personalizadas

config/
├── settings.py             # Pydantic Settings (variables de entorno)
└── constants.py            # Duraciones, colores, defaults
```

---

## 🔧 Stack Tecnológico

| Componente | Tecnología |
|---|---|
| **Lenguaje** | Python 3.10+ |
| **Interfaz** | python-telegram-bot >= 21.0 |
| **LLM** | Groq API (llama-3.3-70b-versatile + fallback llama-3.1-8b-instant) |
| **DB** | aiosqlite + thefuzz |
| **Agenda** | Google Calendar API (Service Account) |
| **Config** | python-dotenv + pydantic-settings |
| **Logs** | structlog |
| **Tests** | pytest + pytest-asyncio + pytest-mock |

---

## 🗺️ Roadmap de Sprints

| Sprint | Foco | Estado |
|---|---|---|
| **Sprint 1** | Fundamentos: Config + DB + Infraestructura | ✅ Completado |
| **Sprint 2** | Motor NLU: Groq Parser (intenciones + edición) | ✅ Completado |
| **Sprint 3** | Google Calendar: CRUD completo + búsquedas | ✅ Completado |
| **Sprint 4** | Telegram Híbrido: menú + flujos interactivos | ✅ Completado |
| **Sprint 5** | Motor de Consultas: filtros + edición inteligente | ✅ Completado |

---

## ✅ Principios de Calidad

| Principio | Aplicación |
|-----------|------------|
| **Modularidad** | Cada skill es un módulo independiente |
| **Type Hints** | Python typing estricto en todo el código |
| **Error Handling** | Excepciones personalizadas, reintentos con backoff |
| **Logging** | Structured logging en todas las capas |
| **Testing** | pytest, mocking de APIs externas, cobertura ≥ 80% |
| **Config segura** | Variables de entorno via .env, nunca hardcoded |
| **Seguridad** | Solo responde al ADMIN_TELEGRAM_ID configurado |
