# 📦 Post-MVP — Backlog de Mejoras Futuras

Ideas y mejoras para implementar después de que el MVP esté funcionando.
Priorizadas por impacto y esfuerzo estimado.

---

## 🔴 Prioridad Alta (Próximas versiones)

### 1. Notificaciones Automáticas
**Descripción:** Enviar recordatorios automáticos por Telegram antes de cada evento.
- Recordatorio 1 hora antes al técnico asignado.
- Recordatorio al inicio del día con el resumen de la agenda.
- Notificación al admin cuando se crea/modifica/cancela un evento.

**Esfuerzo:** Medio  
**Skills necesarias:** Telegram Bot, Scheduler (APScheduler).

---

### 2. Reportes Semanales/Mensuales
**Descripción:** Generar reportes automáticos con estadísticas.
- Cantidad de servicios por tipo.
- Monto total cobrado.
- Servicios pendientes vs completados.
- Cliente con más servicios.

**Esfuerzo:** Medio  
**Formato:** Mensaje de Telegram con tabla formateada o imagen generada.

---

### 3. Historial de Servicios por Cliente
**Descripción:** Poder ver todos los servicios realizados a un cliente.
- Comando: "¿Qué servicios le hicimos a García?"
- Lista cronológica con tipo, fecha, monto.

**Esfuerzo:** Bajo  
**Skills necesarias:** SQLite (JOIN eventos + clientes).

---

## 🟡 Prioridad Media

### 4. Multi-técnico (Asignación de Eventos)
**Descripción:** Asignar eventos a técnicos específicos.
- Tabla `tecnicos` con nombre y especialidad.
- Campo `tecnico_asignado` en eventos.
- Filtrar agenda por técnico.

**Esfuerzo:** Alto

---

### 5. Exportación de Datos
**Descripción:** Exportar clientes y eventos a CSV/Excel.
- Comando `/exportar clientes` → genera CSV.
- Comando `/exportar eventos mes` → genera CSV del mes.

**Esfuerzo:** Bajo

---

### 6. Búsqueda Avanzada de Eventos
**Descripción:** Buscar eventos por rango de fechas, tipo, cliente o estado.
- "Mostrar instalaciones de febrero"
- "¿Cuántos presupuestos hice esta semana?"

**Esfuerzo:** Medio

---

### 7. Fotos como Evidencia
**Descripción:** Almacenar fotos del trabajo realizado en el servidor y
vincularlas al evento.
- Guardar en `data/photos/{evento_id}/`.
- Mostrar thumbnails en el historial del cliente.
- Límite: 5 fotos por evento, máx 5MB cada una.

**Esfuerzo:** Medio

---

## 🟢 Prioridad Baja (Nice to have)

### 8. Dashboard Web Básico
**Descripción:** Interfaz web mínima para ver la agenda en un navegador.
- Solo lectura (la gestión sigue por Telegram).
- Vista de calendario mensual.
- FastAPI + templates HTML o React simple.

**Esfuerzo:** Alto

---

### 9. Multi-calendario
**Descripción:** Soporte para múltiples calendarios de Google Calendar
(un calendario por técnico o por tipo de servicio).

**Esfuerzo:** Alto

---

### 10. Integración con WhatsApp Business API
**Descripción:** Además de Telegram, permitir gestión por WhatsApp.

**Esfuerzo:** Muy Alto

---

### 11. Backup Automático
**Descripción:** Backup diario de la base de datos SQLite.
- Copia de `data/crm.db` a `data/backups/crm_YYYY-MM-DD.db`.
- Retención de últimos 7 backups.
- Cron job o scheduler interno.

**Esfuerzo:** Bajo

---

### 12. Modo Vacaciones
**Descripción:** Bloquear agendamiento en rangos de fechas específicos.
- `/vacaciones 2026-03-15 2026-03-22`
- El bot rechaza eventos en ese rango con mensaje personalizado.

**Esfuerzo:** Bajo

---

## Criterios de Priorización

| Factor     | Peso | Descripción                                       |
| ---------- | ---- | ------------------------------------------------- |
| Impacto    | 40%  | ¿Cuánto mejora la experiencia del usuario?       |
| Esfuerzo   | 30%  | ¿Cuánto tiempo y complejidad requiere?           |
| Riesgo     | 20%  | ¿Puede romper funcionalidad existente?           |
| Dependencia| 10%  | ¿Requiere cambios en la arquitectura base?       |
