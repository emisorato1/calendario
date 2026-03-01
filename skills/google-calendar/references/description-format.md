# Formato de Descripción de Eventos

## Template de Descripción

Cuando se crea un evento en Google Calendar, la descripción sigue un
formato estandarizado que facilita la lectura y el cierre posterior:

```python
def build_event_description(
    tipo_servicio: str,
    direccion: str,
    notas: str = "",
) -> str:
    """Construye la descripción formateada para Google Calendar."""
    return (
        f"📋 Tipo: {tipo_servicio.capitalize()}\n"
        f"📍 Dirección: {direccion}\n"
        f"📝 Notas: {notas or '—'}\n"
        f"\n"
        f"── Post-servicio (completar al terminar) ──\n"
        f"✅ Trabajo realizado: \n"
        f"💰 Monto cobrado: \n"
        f"📝 Notas de cierre: \n"
        f"📷 Fotos: \n"
    )
```

## Template de Cierre

Cuando se completa un evento, se actualiza la descripción:

```python
def build_completed_description(
    tipo_servicio: str,
    direccion: str,
    notas: str,
    trabajo_realizado: str,
    monto_cobrado: float,
    notas_cierre: str = "",
    fotos: list[str] = None,
) -> str:
    """Construye la descripción actualizada al completar un servicio."""
    fotos_text = ", ".join(fotos) if fotos else "—"
    return (
        f"📋 Tipo: {tipo_servicio.capitalize()}\n"
        f"📍 Dirección: {direccion}\n"
        f"📝 Notas: {notas or '—'}\n"
        f"\n"
        f"── Post-servicio ──\n"
        f"✅ Trabajo realizado: {trabajo_realizado}\n"
        f"💰 Monto cobrado: ${monto_cobrado:,.0f}\n"
        f"📝 Notas de cierre: {notas_cierre or '—'}\n"
        f"📷 Fotos: {fotos_text}\n"
    )
```

## Título del Evento

```python
def build_event_title(nombre: str, telefono: str) -> str:
    """Construye el título del evento para Google Calendar."""
    return f"{nombre} — {telefono}"
```

## Ejemplo Completo

**Al crear:**
```
Título:     Juan Pérez — 351-1234567
Ubicación:  Balcarce 132
Descripción:
  📋 Tipo: Instalación
  📍 Dirección: Balcarce 132
  📝 Notas: Poner 3 cámaras y cambiar 1 batería de alarma

  ── Post-servicio (completar al terminar) ──
  ✅ Trabajo realizado: 
  💰 Monto cobrado: 
  📝 Notas de cierre: 
  📷 Fotos: 
```

**Al completar:**
```
Título:     Juan Pérez — 351-1234567  [COLOR: VERDE]
Descripción:
  📋 Tipo: Instalación
  📍 Dirección: Balcarce 132
  📝 Notas: Poner 3 cámaras y cambiar 1 batería de alarma

  ── Post-servicio ──
  ✅ Trabajo realizado: Se instalaron 3 cámaras domo y se cambió batería
  💰 Monto cobrado: $45,000
  📝 Notas de cierre: Cliente satisfecho, queda pendiente revisión en 3 meses
  📷 Fotos: foto1.jpg, foto2.jpg
```
