# Agente Calendario v2

Asistente virtual por Telegram para un tecnico instalador de camaras y alarmas. Gestiona agenda en Google Calendar con interfaz hibrida (botones + lenguaje natural) y CRM local en SQLite.

## Requisitos previos

- Python >= 3.10
- pip

## Instalacion

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd agente-calendario-v2

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Configuracion

```bash
# 1. Copiar el archivo de ejemplo
cp .env.example .env

# 2. Editar con tus credenciales
nano .env
```

Variables obligatorias:

| Variable | Descripcion |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (obtenido via @BotFather) |
| `ADMIN_TELEGRAM_IDS` | IDs de Telegram de los admins (max 2, separados por coma) |
| `GROQ_API_KEY` | API key de Groq (https://console.groq.com) |
| `GOOGLE_CALENDAR_ID` | ID del calendario de Google |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Ruta al JSON de la cuenta de servicio de Google |

## Tests

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar todos los tests
pytest -v

# Ejecutar tests con cobertura
pytest --cov=agents --cov=core --cov=config --cov-report=term-missing

# Tests por modulo
pytest tests/test_config_and_core.py -v        # Config + Core
pytest tests/test_db_manager/ -v               # CRM (SQLite)
pytest tests/test_groq_parser/ -v              # Motor NLU (Groq)
pytest tests/test_calendar_sync/ -v            # Google Calendar
pytest tests/test_work_schedule.py -v          # Motor de horario laboral
pytest tests/test_orchestrator.py -v           # Orquestador central
pytest tests/test_telegram_listener/ -v        # Bot Telegram (filtros, teclados, handler)

# Generar reporte de cobertura en HTML
pytest --cov=agents --cov=core --cov=config --cov-report=html
# Abrir htmlcov/index.html en el navegador
```

Cobertura minima requerida: **80%** (configurado en `pyproject.toml`).

## Estructura del proyecto

```
agente-calendario-v2/
├── agents/                     # Modulos de negocio
│   ├── db_manager/             # CRM SQLite (CRUD + fuzzy search)
│   ├── groq_parser/            # Motor NLU via Groq API
│   ├── calendar_sync/          # Google Calendar (CRUD + busquedas + colores)
│   └── telegram_listener/      # Bot Telegram (filtros, teclados, handler)
├── config/
│   ├── settings.py             # Configuracion (pydantic-settings)
│   └── constants.py            # Constantes del dominio
├── core/
│   ├── orchestrator.py         # Orquestador central
│   ├── work_schedule.py        # Motor de horario laboral
│   ├── exceptions.py           # Excepciones personalizadas
│   └── logger.py               # Logging estructurado (structlog)
├── tests/                      # Suite de tests (pytest + pytest-asyncio)
├── specs/                      # Especificaciones por sprint
├── main.py                     # Entry point del bot
├── .env.example                # Template de variables de entorno
├── pyproject.toml              # Config de pytest, coverage, ruff
└── requirements.txt            # Dependencias Python
```

## Stack tecnologico

| Componente | Tecnologia |
|---|---|
| Lenguaje | Python 3.10+ |
| Interfaz | python-telegram-bot >= 21.0 |
| LLM / NLU | Groq API (llama-3.3-70b-versatile + fallback) |
| Base de datos | aiosqlite + thefuzz (busqueda difusa) |
| Agenda | Google Calendar API (Service Account) |
| Configuracion | pydantic-settings + python-dotenv |
| Logs | structlog |
| Tests | pytest + pytest-asyncio + pytest-cov + pytest-mock |

## Ejecucion

```bash
# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar el bot
python main.py
```

El bot arrancara en modo polling. Para detenerlo, usar Ctrl+C (SIGINT).

## Roadmap

| Sprint | Foco | Estado |
|---|---|---|
| Sprint 1 | Fundamentos: Config + DB + Infraestructura | Completado |
| Sprint 2 | Motor NLU: Groq Parser (intenciones + edicion) | Completado |
| Sprint 3 | Google Calendar: CRUD completo + busquedas | Completado |
| Sprint 4 | Telegram Hibrido: menu + flujos interactivos | Completado |
| Sprint 5 | Motor de Consultas: filtros + edicion inteligente | Completado |





detecciones de fallas:

## Crear turno
