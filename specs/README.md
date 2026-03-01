# 📋 Especificaciones del Proyecto — Agente Calendario

Este directorio contiene las especificaciones técnicas organizadas por sprints.

## Estructura

```
specs/
├── README.md                 ← Este archivo
├── diagram.md                ← Diagrama de arquitectura y flujos
├── sprint-1/
│   ├── config-core.md        ← Configuración, logging, excepciones
│   └── database-setup.md     ← Modelos, migrations, repository, caché
├── sprint-2/
│   └── llm-parser.md         ← Parser LLM con Groq + fallback
├── sprint-3/
│   └── google-calendar.md    ← Integración con Google Calendar API
├── sprint-4/
│   └── telegram-bot.md       ← Bot de Telegram: menú, handlers, flujos
├── sprint-5/
│   └── orchestrator.md       ← Orquestador: integración completa + cierre
└── post-mvp/
    └── backlog.md            ← Ideas y mejoras futuras
```

## Convenciones

- Cada spec es un archivo Markdown autocontenido.
- Cada spec referencia las skills relevantes del directorio `skills/`.
- Los objetivos se escriben con criterio **SMART** (Specific, Measurable, Achievable, Relevant, Time-bound).
- Los pasos de implementación son lo suficientemente detallados para
  ser ejecutables sin ambigüedad.

## Roadmap

| Sprint   | Nombre                      | Dependencias | Spec       | Implementación |
| -------- | --------------------------- | ------------ | ---------- | -------------- |
| Sprint 1 | Core & Database             | —            | ✅ Done    | ⬜ Pendiente   |
| Sprint 2 | LLM Parser                  | Sprint 1     | ✅ Done    | ⬜ Pendiente   |
| Sprint 3 | Google Calendar             | Sprint 1     | ✅ Done    | ⬜ Pendiente   |
| Sprint 4 | Telegram Bot                | Sprint 1-3   | ✅ Done    | ⬜ Pendiente   |
| Sprint 5 | Orquestador & Integración   | Sprint 1-4   | ✅ Done    | ⬜ Pendiente   |
| Post-MVP | Mejoras y extras            | Sprint 1-5   | ✅ Done    | ⬜ Backlog     |

## Estado de Skills (Documentación)

| Skill                  | SKILL.md | Referencias | Estado   |
| ---------------------- | -------- | ----------- | -------- |
| config-observability   | ✅       | 3/3         | ✅ Done  |
| sqlite-database        | ✅       | 4/4         | ✅ Done  |
| llm-parser             | ✅       | 4/4         | ✅ Done  |
| google-calendar        | ✅       | 3/3         | ✅ Done  |
| telegram-bot           | ✅       | 4/4         | ✅ Done  |
| orchestrator           | ✅       | 3/3         | ✅ Done  |

## Principios de Diseño Aplicados

Todas las specs siguen estos principios:

- **KISS**: La solución más simple que funcione.
- **SOLID**: Responsabilidad única por módulo.
- **DRY**: Reutilización de lógica y templates.
- **Fail-Safe**: Fallbacks y manejo de errores en todo nivel.
- **Test-Driven**: Tests unitarios para toda función crítica.
