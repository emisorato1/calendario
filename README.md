# 📅 Agente Calendario

> **Bot de Telegram con IA** para gestión integral de servicios técnicos:
> agenda, clientes, Google Calendar y cierre de trabajos — todo desde una conversación natural.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 Descripción

Agente Calendario es un bot de Telegram que funciona como asistente virtual
inteligente para empresas de servicios técnicos (cámaras de seguridad, alarmas,
porteros eléctricos, software, etc.).

Permite gestionar la agenda mediante **botones interactivos** o **mensajes en
lenguaje natural**, manteniendo sincronizados una **base de datos SQLite** y un
**Google Calendar** compartido.

### ✨ Características Principales

- 🤖 **Lenguaje Natural**: Escribí "Agendar instalación mañana a las 10 para
  Juan" y el bot entiende todo.
- 📅 **Google Calendar**: Los eventos se crean con colores por tipo de servicio.
- 🗄️ **CRM Liviano**: Base de datos SQLite con clientes y historial.
- ✅ **Cierre de Servicios**: Registrá trabajo realizado, monto cobrado y fotos.
- 🔐 **Roles**: Admin y Editor con permisos diferenciados.
- ♻️ **Resiliencia**: Fallback de LLM (Groq → Gemini → OpenAI), reintentos automáticos.
- 💻 **Recursos Mínimos**: Corre en un Ubuntu Server con hardware básico.

---

## 🚀 Inicio Rápido

### Requisitos Previos

- **Python 3.11** o superior
- **pip** (gestor de paquetes de Python)
- **Cuenta de Telegram** + Token de Bot (vía [@BotFather](https://t.me/BotFather))
- **Cuenta de Google Cloud** con Calendar API habilitada + Service Account
- **API Key de Groq** (gratuito en [console.groq.com](https://console.groq.com))

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/agente-calendario.git
cd agente-calendario
```

### 2. Crear Entorno Virtual

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 3. Instalar Dependencias

```bash
pip install -e ".[dev]"
```

> Si no tenés `pyproject.toml` aún, instalá manualmente:
> ```bash
> pip install python-telegram-bot pydantic pydantic-settings aiosqlite \
>             groq google-api-python-client google-auth "thefuzz[speedup]" \
>             python-dotenv pytest pytest-asyncio pytest-cov
> ```

### 4. Configurar Variables de Entorno

```bash
cp .env.example .env
```

Editá `.env` con tus datos reales:

```env
# Obligatorios
TELEGRAM_BOT_TOKEN=tu_token_aqui
ADMIN_TELEGRAM_IDS=[tu_telegram_id]
GROQ_API_KEY=gsk_tu_api_key
GOOGLE_CALENDAR_ID=tu_calendar_id@group.calendar.google.com
GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service_account.json
```

> **Tip:** Para obtener tu Telegram ID, usá [@userinfobot](https://t.me/userinfobot).

### 5. Configurar Google Calendar

1. Ir a [Google Cloud Console](https://console.cloud.google.com).
2. Crear un proyecto o seleccionar uno existente.
3. Habilitar **Google Calendar API**.
4. Crear una **Service Account** y descargar la clave JSON.
5. Guardar el archivo como `credentials/service_account.json`.
6. En Google Calendar, compartir el calendario con el email de la Service Account
   (con permisos de "Hacer cambios en eventos").

### 6. Ejecutar el Bot

```bash
python -m src.main
```

Deberías ver:
```
[2026-03-01 12:00:00] INFO  src.main  │ Configuración validada correctamente
[2026-03-01 12:00:00] INFO  src.main  │ Base de datos inicializada
[2026-03-01 12:00:00] INFO  src.main  │ Bot iniciado. Esperando mensajes...
```

### 7. Probar el Bot

1. Abrir Telegram y buscar tu bot.
2. Enviar `/start` — deberías ver el menú de botones.
3. Probar: "Agendar instalación de cámaras para Juan Pérez mañana a las 10,
   Balcarce 132, tel 351-1234567".

---

## 🧪 Tests

### Ejecutar todos los tests

```bash
pytest
```

### Ejecutar con cobertura

```bash
pytest --cov=src --cov-report=term-missing
```

### Ejecutar solo tests unitarios

```bash
pytest tests/unit/
```

### Ejecutar solo tests de integración

```bash
pytest tests/integration/
```

### Ejecutar un test específico

```bash
pytest tests/unit/test_config.py -v
```

---

## 📁 Estructura del Proyecto

```
agente-calendario/
├── .env                        # Variables de entorno (no versionado)
├── .env.example                # Plantilla de variables
├── credentials/                # Service Account de Google (no versionado)
│   └── service_account.json
├── src/                        # Código fuente
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuración centralizada (Pydantic)
│   ├── core/                   # Logging, excepciones
│   ├── bot/                    # Telegram handlers y menús
│   ├── llm/                    # Parser LLM (Groq / Gemini)
│   ├── calendar_api/           # Google Calendar wrapper
│   ├── db/                     # Modelos, repositorio, caché
│   └── orchestrator/           # Lógica de negocio central
├── tests/                      # Tests unitarios y de integración
│   ├── unit/
│   └── integration/
├── skills/                     # Documentación técnica por módulo
├── specs/                      # Especificaciones por sprint
├── data/                       # SQLite DB (auto-generado)
├── logs/                       # Archivos de log (auto-generado)
├── pyproject.toml              # Dependencias y metadata
└── README.md                   # Este archivo
```

---

## 🎨 Tipos de Servicio y Colores

| Tipo             | Color en Calendar  | Emoji |
| ---------------- | ------------------ | ----- |
| Instalación      | 🔵 Azul            | 🔵    |
| Revisión         | 🟡 Amarillo        | 🟡    |
| Mantenimiento    | 🟠 Naranja         | 🟠    |
| Reparación       | 🟠 Naranja         | 🟠    |
| Presupuesto      | 🟡 Amarillo        | 🟡    |
| Otro             | ⚪ Gris            | ⚪    |
| Completado       | 🟢 Verde           | 🟢    |

---

## 🔐 Roles y Permisos

| Acción            | Admin | Editor |
| ----------------- | ----- | ------ |
| Crear Evento      | ✅     | ❌      |
| Editar Evento     | ✅     | ✅      |
| Ver Eventos       | ✅     | ✅      |
| Eliminar Evento   | ✅     | ❌      |
| Terminar Evento   | ✅     | ✅      |
| Ver Contactos     | ✅     | ✅      |
| Editar Contacto   | ✅     | ❌      |

---

## 📋 Roadmap

| Sprint   | Entregable                                  | Spec           | Implementación |
| -------- | ------------------------------------------- | -------------- | -------------- |
| Sprint 1 | Configuración, DB, modelos, repositorio     | ✅ Done        | ⬜ Pendiente   |
| Sprint 2 | Parser LLM (Groq) con fallback              | ✅ Done        | ⬜ Pendiente   |
| Sprint 3 | Google Calendar: CRUD de eventos             | ✅ Done        | ⬜ Pendiente   |
| Sprint 4 | Bot Telegram: menú, handlers, flujos         | ✅ Done        | ⬜ Pendiente   |
| Sprint 5 | Orquestador: integración completa            | ✅ Done        | ⬜ Pendiente   |
| Post-MVP | Notificaciones, reportes, dashboard          | ✅ Done        | ⬜ Backlog     |

Ver [specs/README.md](specs/README.md) para las especificaciones detalladas.

---

## 📚 Documentación

| Recurso | Descripción |
|---------|-------------|
| [Documento del Proyecto](idea_general_proyecto.md) | Visión completa, arquitectura, casos de uso |
| [Skills](skills/) | Módulos de conocimiento técnico |
| [Specs](specs/README.md) | Especificaciones por sprint |
| [Backlog Post-MVP](specs/post-mvp/backlog.md) | Mejoras futuras priorizadas |

---

## 🛠️ Desarrollo

### Agregar un nuevo tipo de servicio

1. Agregar al enum `TipoServicio` en `src/db/models.py`.
2. Agregar el color en `src/calendar_api/colors.py`.
3. Actualizar el CHECK constraint en el schema SQL.
4. Actualizar los prompts del LLM en `src/llm/prompts.py`.

### Agregar un nuevo handler de Telegram

1. Crear `src/bot/handlers/nuevo_handler.py`.
2. Implementar `get_conversation_handler()`.
3. Registrar en `src/bot/app.py`.
4. Agregar tests en `tests/unit/test_nuevo_handler.py`.

---

## ⚙️ Variables de Entorno

| Variable                     | Requerida | Default                              | Descripción                    |
| ---------------------------- | --------- | ------------------------------------ | ------------------------------ |
| `TELEGRAM_BOT_TOKEN`        | ✅         | —                                    | Token del bot de Telegram      |
| `ADMIN_TELEGRAM_IDS`        | ✅         | —                                    | IDs de admins (formato JSON)   |
| `EDITOR_TELEGRAM_IDS`       | ❌         | `[]`                                 | IDs de editors (formato JSON)  |
| `GROQ_API_KEY`              | ✅         | —                                    | API key de Groq                |
| `GROQ_MODEL_PRIMARY`        | ❌         | `llama-3.3-70b-versatile`            | Modelo LLM primario            |
| `GROQ_MODEL_FALLBACK`       | ❌         | `llama-3.1-8b-instant`               | Modelo LLM de respaldo         |
| `GOOGLE_CALENDAR_ID`        | ✅         | —                                    | ID del calendario de Google    |
| `GOOGLE_SERVICE_ACCOUNT_PATH`| ❌        | `credentials/service_account.json`   | Ruta al archivo de credenciales|
| `SQLITE_DB_PATH`            | ❌         | `data/crm.db`                        | Ruta de la base de datos       |
| `TIMEZONE`                   | ❌         | `America/Argentina/Buenos_Aires`     | Zona horaria                   |
| `LOG_LEVEL`                  | ❌         | `DEBUG`                              | Nivel de logging               |

---

## 📄 Licencia

Este proyecto es de uso privado. Todos los derechos reservados.
