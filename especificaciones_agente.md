# Especificaciones del Proyecto: Asistente IA + CRM Local para Servicio Técnico

> **Versión**: 2.1  
> **Fecha**: 2026-02-28  
> **Estado**: En desarrollo

---

## 1. Descripción General

Agente de IA en Python que funciona como asistente virtual por Telegram para un técnico instalador de cámaras de seguridad y alarmas. Gestiona la agenda mediante Google Calendar y mantiene un CRM local en SQLite. Opera para dos tipos de usuarios configurables por ID de Telegram.

El bot combina una **interfaz híbrida** (menú de botones + lenguaje natural) con un motor de IA (Groq LLM) para interpretar instrucciones, extraer datos estructurados, y ejecutar operaciones completas sobre la agenda: crear, editar, cancelar y consultar eventos.

---

## 2. Arquitectura y Entorno de Ejecución

| Componente | Detalle |
|---|---|
| **Host** | Servidor local propio (Ubuntu Server, Headless) |
| **Lenguaje** | Python 3.10+ |
| **Conexión Telegram** | Long Polling (sin webhooks, sin puertos abiertos) |
| **Base de Datos** | SQLite (archivo `.db` local, sin servidores externos) |
| **Zona Horaria** | `America/Argentina/Buenos_Aires` (UTC-3) |

---

## 2.1 Sistema de Roles y Permisos

El bot responde **únicamente** a Telegram IDs que estén registrados en alguno de los dos roles. Cualquier otro usuario es ignorado (sin respuesta, con log de advertencia).

### Rol: Admin

- **Cantidad de cuentas**: Hasta 2 IDs de Telegram (configurables en `.env`).
- **Acceso**: Completo — puede crear, editar, cancelar y consultar eventos.
- **Menú que ve**:
  ```
  [ 📅 Crear Turno ]  [ 📋 Listar Eventos ]
  [ ✏️ Editar Evento ] [ 🚫 Cancelar Evento ]
  ```
- **Configuración**: `ADMIN_TELEGRAM_IDS=123456789,987654321` (lista separada por comas).

### Rol: Editor

- **Cantidad de cuentas**: Una o más IDs de Telegram (configurables en `.env`).
- **Acceso limitado**: Solo puede **editar** eventos existentes y **consultar/listar** la agenda. **No puede crear ni cancelar eventos.**
- **Menú que ve**:
  ```
  [ ✏️ Editar Evento ] [ 📋 Listar Eventos ]
  ```
- **Configuración**: `EDITOR_TELEGRAM_IDS=111222333,444555666` (lista separada por comas, puede estar vacía).

### Tabla de Permisos

| Acción | Admin | Editor |
|---|:---:|:---:|
| Crear turno (texto o botón) | ✅ | ❌ |
| Listar eventos (cualquier filtro) | ✅ | ✅ |
| Editar evento (selección + NLU) | ✅ | ✅ |
| Cancelar evento (interactivo) | ✅ | ❌ |
| Comandos `/start`, `/help` | ✅ | ✅ |
| Comandos `/status`, `/clientes` | ✅ | ❌ |

### Comportamiento ante acceso denegado

- Si un **Editor** intenta crear o cancelar (por texto o mediante comandos directos), el bot responde: *"No tenés permiso para realizar esa acción."*
- Si un **usuario desconocido** escribe al bot, este lo **ignora silenciosamente** (no responde, pero loguea el intento a nivel `WARNING`).

---

## 3. Stack Tecnológico

| Componente | Tecnología |
|---|---|
| **Interfaz** | `python-telegram-bot >= 21.0` |
| **LLM (Cerebro)** | Groq API — `llama-3.3-70b-versatile` (primario) + `llama-3.1-8b-instant` (fallback) |
| **Agenda** | Google Calendar API (Service Account) |
| **Base de Datos** | `aiosqlite` + `thefuzz` (fuzzy search) |
| **Config** | `pydantic-settings` + `python-dotenv` |
| **Logs** | `structlog` |
| **Tests** | `pytest` + `pytest-asyncio` + `pytest-mock` |

---

## 4. Interfaz de Usuario: Modo Híbrido

El bot opera en **dos modos simultáneos** que coexisten:

### 4.1 Menú de Botones (ReplyKeyboard persistente)

Siempre visible en el teclado del usuario, adaptado según su rol:

**Admin** (4 botones):
```
[ 📅 Crear Turno ]  [ 📋 Listar Eventos ]
[ ✏️ Editar Evento ] [ 🚫 Cancelar Evento ]
```

**Editor** (2 botones):
```
[ ✏️ Editar Evento ] [ 📋 Listar Eventos ]
```

### 4.2 Lenguaje Natural Directo

El usuario puede escribir una instrucción libre en cualquier momento sin tocar los botones. El LLM interpreta la intención y ejecuta el flujo correspondiente.

**Ejemplos:**
- *"Agendame para mañana a las 10 una instalación en lo de García"* → flujo de creación
- *"Cancelá lo de López"* → flujo de cancelación interactiva
- *"Qué tengo para el lunes?"* → listado del día
- *"¿Cuándo tengo turno con Martínez?"* → listado por cliente

---

## 5. Funcionalidades y Flujos Detallados

### 5.1 Creación de Turno

**Disparador:** Botón `📅 Crear Turno` (solo Admin) o mensaje de texto con intención `agendar`.

**Flujo:**
1. Al presionar el botón, el bot muestra **inmediatamente** un cartel de ayuda rápida:
   ```
   📅 *Nuevo turno*
   
   Contáme sobre el turno que querés agendar.
   Podés escribir de forma natural, por ejemplo:
   
   • _"Reunión de instalación en lo de García el lunes a las 10"_
   • _"Revisión en casa de López, mañana 14:00"_
   • _"Presupuesto para Martínez, viernes 9:30"_
   
   💡 Cuanto más detallés (cliente, servicio, fecha, hora), más rápido proceso el turno.
   ```
2. Usuario escribe la descripción del turno en lenguaje natural.
3. LLM extrae: cliente, tipo de servicio, fecha, hora, dirección (opcional), teléfono (opcional).
4. CRM: búsqueda fuzzy del cliente. Si existe, recupera dirección y teléfono. Si no, lo crea.
5. Google Calendar: verificar conflictos en el rango `[hora_inicio - 30min, hora_fin + 30min]`.
6. Bot muestra **resumen del evento** con teclado inline `[✅ Confirmar] [❌ Cancelar]`.
7. Usuario confirma → evento creado en Calendar + servicio registrado en historial.

**Formato del resumen:**
```
📋 *Resumen del evento*

🔧 Tipo: Instalación de cámaras
👤 Cliente: Carlos García (recurrente ✅)
📅 Fecha: Martes 03/03/2026
🕐 Hora: 10:00 - 13:00 (3h)
📍 Dirección: Av. San Martín 456 (de BD)
📞 Teléfono: 260-4567890 (de BD)
🎨 Color: 🔵 Azul

¿Confirmar este evento?
[✅ Confirmar] [❌ Cancelar]
```

---

### 5.2 Cancelación Interactiva

**Disparador:** Botón `🚫 Cancelar Evento` o mensaje con intención `cancelar`.

**Flujo:**
1. Bot consulta Google Calendar y muestra la **lista de próximos eventos pendientes** (máx. 10, ordenados por fecha).
2. Formato de lista:
   ```
   🗓️ *Seleccioná el evento a cancelar:*

   1️⃣ Lun 02/03 — 09:00 | Revisión — García, Juan
   2️⃣ Mar 03/03 — 10:00 | Instalación de cámaras — López, Pedro
   3️⃣ Vie 06/03 — 14:00 | Mantenimiento — Martínez, Carlos
   ```
   Botones inline numerados: `[1]`, `[2]`, `[3]`, ...
3. Usuario selecciona el número → Bot pide confirmación final: `"¿Eliminás Revisión — García, Juan del Lun 02/03? [✅ Sí, eliminar] [❌ No, volver]"`
4. Confirmado → evento eliminado del Calendar.

> ⚠️ **El bot nunca borra nada sin mostrar la lista y solicitar confirmación explícita.**

---

### 5.3 Edición Inteligente

**Disparador:** Botón `✏️ Editar Evento` o mensaje con intención `editar`.

**Flujo:**
1. Bot muestra la **lista de próximos eventos pendientes** (mismo formato que cancelación).
2. Usuario selecciona el evento a modificar.
3. Bot responde: *"¿Qué querés cambiar? Escribilo en lenguaje natural."*
4. Usuario escribe la modificación libre:
   - *"Pasalo para el viernes a las 16"*
   - *"Cambiá el servicio a instalación de cámaras"*
   - *"Actualizá el teléfono a 260-1234567"*
5. LLM interpreta la instrucción, identifica qué campo/s cambiar y produce un `EditInstruction` (JSON estructurado con los campos a patchear).
6. Bot muestra resumen de los cambios y pide confirmación: `[✅ Aplicar cambios] [❌ Cancelar]`.
7. Confirmado → PATCH del evento en Google Calendar.

---

### 5.4 Consultas y Listados

**Disparador:** Botón `📋 Listar Eventos` o mensajes con intención de consulta.

El sistema diferencia automáticamente **4 tipos de listado**:

#### A) Todos los eventos pendientes
- *"¿Qué tengo pendiente?"*, *"Listar eventos"*
- Muestra todos los eventos futuros desde hoy, hasta 30 días adelante.

#### B) Historial de eventos realizados
- *"¿Qué hice la semana pasada?"*, *"Mostrame el historial"*
- Muestra eventos pasados (los últimos 30 días o configurables).

#### C) Agenda de un día específico
- *"¿Qué tengo el lunes?"*, *"Dame la agenda del viernes"*
- Muestra todos los eventos de esa fecha.

#### D) Turnos de un cliente específico
- *"¿Cuándo tengo que ir a lo de Juan?"*, *"Turnos de García"*
- Cruza datos de Calendar con el nombre del cliente (fuzzy match).

**Formato de listado estándar:**
```
📅 *Eventos pendientes (5):*

📌 Lun 02/03 | 09:00 - 10:00 | 🟡 Revisión — García, Juan
📌 Mar 03/03 | 10:00 - 13:00 | 🔵 Instalación — López, Pedro
📌 Vie 06/03 | 14:00 - 16:00 | 🟠 Mantenimiento — Martínez, Carlos
```

---

## 6. Modelo de Datos (Esquema SQLite)

```sql
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    alias TEXT,
    telefono TEXT,
    direccion TEXT,
    ciudad TEXT DEFAULT 'San Rafael',
    notas_equipamiento TEXT,
    fecha_alta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historial_servicios (
    id_servicio INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente INTEGER NOT NULL,
    calendar_event_id TEXT,
    fecha_servicio DATETIME,
    tipo_trabajo TEXT,
    descripcion TEXT,
    estado TEXT DEFAULT 'pendiente',  -- 'pendiente' | 'realizado' | 'cancelado'
    FOREIGN KEY(id_cliente) REFERENCES clientes(id_cliente)
);
```

---

## 7. Modelo de Evento en Google Calendar

| Campo | Valor |
|---|---|
| **Título** | `{nombre_cliente} - {telefono}` |
| **Ubicación** | Dirección del cliente (BD > Mensaje) |
| **Descripción** | Tipo de Servicio \| Notas: Creado vía IA \| Descripción del trabajo a realizar \| Resultados \| Materiales/Equipos utilizados \| Códigos de cámaras/alarmas |
| **Color: Servicios** (reparación, fallas, mantenimiento) | `"6"` — Mandarina/Naranja |
| **Color: Trabajos** (instalaciones) | `"9"` — Arándano/Azul |
| **Color: Presupuestos/revisiones** | `"5"` — Plátano/Amarillo |
| **Color: Otros** | `"8"` — Grafito |

---

## 8. Esquema de Intenciones del LLM

El LLM detecta las siguientes intenciones:

| Intención | Descripción |
|---|---|
| `agendar` | Crear un nuevo turno/evento |
| `cancelar` | Eliminar un evento (dispara flujo interactivo) |
| `editar` | Modificar un evento existente (dispara flujo de selección + NLU) |
| `listar_pendientes` | Ver todos los eventos futuros |
| `listar_historial` | Ver eventos pasados |
| `listar_dia` | Ver agenda de un día específico |
| `listar_cliente` | Ver turnos de un cliente en particular |
| `otro` | Intención no reconocida → respuesta amable |

---

## 9. Comandos de Telegram

| Comando | Roles con acceso | Descripción |
|---|:---:|---|
| `/start` | Admin + Editor | Mensaje de bienvenida + menú según rol |
| `/help` | Admin + Editor | Lista de capacidades según rol |
| `/status` | Solo Admin | Estado del sistema (DB, Calendar, Groq, uptime) |
| `/clientes` | Solo Admin | Últimos 10 clientes con fecha de último servicio |

---

## 10. Principios de Calidad

| Principio | Aplicación |
|---|---|
| **Modularidad** | Cada skill es un módulo independiente en `agents/` |
| **Type Hints** | Python typing estricto en todo el código |
| **Error Handling** | Excepciones personalizadas, reintentos con backoff exponencial |
| **Logging** | Structured logging (`structlog`) en todas las capas |
| **Testing** | pytest + mocking de APIs externas, cobertura ≥ 80% |
| **Config segura** | Variables de entorno vía `.env`, nunca hardcoded |
| **Seguridad** | Solo responde a IDs en `ADMIN_TELEGRAM_IDS` y `EDITOR_TELEGRAM_IDS` |