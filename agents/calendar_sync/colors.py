"""Colores de Google Calendar según tipo de servicio.

Delega a las constantes definidas en config/constants.py para evitar duplicación.
"""

from __future__ import annotations

from config.constants import COLOR_EMOJI, COLOR_MAP


def get_color_id(tipo_servicio: str) -> str:
    """Retorna el colorId de Google Calendar para un tipo de servicio.

    Args:
        tipo_servicio: Tipo de servicio (instalacion, revision, etc.).

    Returns:
        ID de color de Google Calendar (string numérico).
    """
    return COLOR_MAP.get(tipo_servicio.lower(), COLOR_MAP["otro"])


def get_color_emoji(tipo_servicio: str) -> str:
    """Retorna el emoji de color para mostrar en Telegram.

    Args:
        tipo_servicio: Tipo de servicio (instalacion, revision, etc.).

    Returns:
        Emoji de color correspondiente al tipo de servicio.
    """
    color_id = get_color_id(tipo_servicio)
    return COLOR_EMOJI.get(color_id, "⚫")
