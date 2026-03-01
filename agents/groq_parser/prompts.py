"""Prompts y templates para el Motor NLU (Groq Parser)."""
from __future__ import annotations

import json

# ── System Prompt — Parseo General ──────────────────────────────────────────

SYSTEM_PROMPT_PARSE = (
    "Eres el asistente de agenda de un técnico instalador de cámaras y alarmas "
    "en Argentina (San Rafael, Mendoza).\n"
    "Tu tarea es analizar mensajes de texto y devolver SIEMPRE un JSON válido "
    "con la estructura indicada.\n"
    "Fecha y hora actual: {fecha_actual} {hora_actual} "
    "(zona horaria: America/Argentina/Buenos_Aires).\n"
    "Servicios disponibles: instalacion, revision, mantenimiento, presupuesto, "
    "reparacion, otro.\n"
    "Intenciones posibles: agendar, cancelar, editar, listar_pendientes, "
    "listar_historial, listar_dia, listar_cliente, otro.\n"
    "REGLAS: No inventes datos. Si un campo no está en el mensaje, ponlo en null. "
    "Resuelve fechas relativas (hoy, mañana, el lunes) usando la fecha actual.\n"
    "Si el usuario indica urgencia (ej: 'es urgente', 'para ya'), "
    "pon urgente en true."
)

# ── System Prompt — Edición ─────────────────────────────────────────────────

SYSTEM_PROMPT_EDIT = (
    "Eres el asistente de agenda. El usuario quiere modificar un evento existente.\n"
    "Evento actual: {evento_actual_json}\n"
    "Instrucción del usuario: {instruccion}\n"
    "Devuelve un JSON con SOLO los campos que deben cambiar. "
    "Usa null para los que NO cambian.\n"
    "Campos posibles: nueva_fecha, nueva_hora, nuevo_tipo_servicio, "
    "nueva_direccion, nuevo_telefono, nueva_duracion_horas.\n"
    "Fecha y hora actual: {fecha_actual} {hora_actual} "
    "(zona horaria: America/Argentina/Buenos_Aires).\n"
    "Resuelve fechas relativas (mañana, el viernes, el lunes que viene) "
    "usando la fecha actual."
)

# ── User Prompt Templates ──────────────────────────────────────────────────


def build_parse_prompt(mensaje: str, fecha_actual: str, hora_actual: str) -> str:
    """Construye el prompt de usuario para parsear un mensaje.

    Args:
        mensaje: Texto del usuario a analizar.
        fecha_actual: Fecha actual en formato 'YYYY-MM-DD'.
        hora_actual: Hora actual en formato 'HH:MM'.

    Returns:
        Tupla (system_prompt, user_prompt) lista para enviar al LLM.
    """
    system = SYSTEM_PROMPT_PARSE.format(
        fecha_actual=fecha_actual,
        hora_actual=hora_actual,
    )
    user = (
        f"Analiza el siguiente mensaje y devuelve el JSON correspondiente:\n\n"
        f'"{mensaje}"'
    )
    return system, user


def build_edit_prompt(
    evento_actual: dict,
    instruccion: str,
    fecha_actual: str,
    hora_actual: str,
) -> str:
    """Construye el prompt para interpretar una instrucción de edición.

    Args:
        evento_actual: Diccionario con los datos del evento a modificar.
        instruccion: Texto del usuario con la instrucción de cambio.
        fecha_actual: Fecha actual en formato 'YYYY-MM-DD'.
        hora_actual: Hora actual en formato 'HH:MM'.

    Returns:
        Tupla (system_prompt, user_prompt) lista para enviar al LLM.
    """
    system = SYSTEM_PROMPT_EDIT.format(
        evento_actual_json=json.dumps(evento_actual, ensure_ascii=False),
        instruccion=instruccion,
        fecha_actual=fecha_actual,
        hora_actual=hora_actual,
    )
    user = (
        f"Instrucción de edición:\n\n"
        f'"{instruccion}"'
    )
    return system, user
