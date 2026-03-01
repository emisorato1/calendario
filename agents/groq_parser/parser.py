"""Pipeline NLU: parseo de mensajes e instrucciones de edición."""
from __future__ import annotations

import json
from datetime import date, datetime

from config.constants import TIMEZONE
from core.exceptions import GroqParsingError
from core.logger import get_logger

from .client import GroqClient
from .prompts import build_edit_prompt, build_parse_prompt
from .schemas import EditInstruction, ParsedMessage

log = get_logger(__name__)


def _get_now() -> tuple[str, str]:
    """Retorna (fecha_str, hora_str) en la zona horaria del proyecto."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # Python 3.8

    now = datetime.now(ZoneInfo(TIMEZONE))
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")


async def parse_message(
    text: str,
    client: GroqClient,
    fecha_actual: date | None = None,
) -> ParsedMessage:
    """Pipeline: componer prompt → llamar LLM → parsear JSON → validar schema.

    Si Pydantic falla, reintenta hasta 2 veces con el mensaje de error incluido
    en el prompt para que el LLM se corrija.

    Args:
        text: Mensaje de texto natural del usuario.
        client: Instancia de GroqClient configurada.
        fecha_actual: Fecha a usar como "hoy". Si es None, usa datetime.now().

    Returns:
        ParsedMessage validado.

    Raises:
        GroqParsingError: Si después de 3 intentos la respuesta no es válida.
    """
    if fecha_actual is not None:
        fecha_str = fecha_actual.strftime("%Y-%m-%d")
        hora_str = "12:00"  # hora por defecto en tests
    else:
        fecha_str, hora_str = _get_now()

    system_prompt, user_prompt = build_parse_prompt(text, fecha_str, hora_str)

    last_error: str | None = None
    max_attempts = 3  # 1 intento original + 2 reintentos

    for attempt in range(max_attempts):
        prompt = user_prompt
        if last_error:
            prompt += (
                f"\n\n[ERROR EN INTENTO ANTERIOR: {last_error}. "
                f"Corrige el JSON y devuélvelo de nuevo.]"
            )

        raw = await client.call(
            system_prompt=system_prompt,
            user_prompt=prompt,
            response_format=ParsedMessage,
        )

        try:
            parsed = ParsedMessage.model_validate(raw)
            log.info(
                "parse_message_ok",
                intencion=parsed.intencion.value,
                attempt=attempt + 1,
            )
            return parsed
        except Exception as exc:
            last_error = str(exc)
            log.warning(
                "parse_message_validation_error",
                attempt=attempt + 1,
                error=last_error,
            )

    raise GroqParsingError(
        f"No se pudo parsear el mensaje después de {max_attempts} intentos. "
        f"Último error: {last_error}"
    )


async def parse_edit_instruction(
    instruccion: str,
    evento_actual: dict,
    client: GroqClient,
    fecha_actual: date | None = None,
) -> EditInstruction:
    """Pipeline para interpretar una instrucción de edición.

    Args:
        instruccion: Texto del usuario con la instrucción de cambio.
        evento_actual: Diccionario con los datos del evento existente.
        client: Instancia de GroqClient configurada.
        fecha_actual: Fecha a usar como "hoy". Si es None, usa datetime.now().

    Returns:
        EditInstruction validado.

    Raises:
        GroqParsingError: Si después de 3 intentos la respuesta no es válida.
    """
    if fecha_actual is not None:
        fecha_str = fecha_actual.strftime("%Y-%m-%d")
        hora_str = "12:00"
    else:
        fecha_str, hora_str = _get_now()

    system_prompt, user_prompt = build_edit_prompt(
        evento_actual=evento_actual,
        instruccion=instruccion,
        fecha_actual=fecha_str,
        hora_actual=hora_str,
    )

    last_error: str | None = None
    max_attempts = 3

    for attempt in range(max_attempts):
        prompt = user_prompt
        if last_error:
            prompt += (
                f"\n\n[ERROR EN INTENTO ANTERIOR: {last_error}. "
                f"Corrige el JSON y devuélvelo de nuevo.]"
            )

        raw = await client.call(
            system_prompt=system_prompt,
            user_prompt=prompt,
            response_format=EditInstruction,
        )

        try:
            edit = EditInstruction.model_validate(raw)
            log.info(
                "parse_edit_ok",
                campos_modificados=[
                    k for k, v in edit.model_dump().items() if v is not None
                ],
                attempt=attempt + 1,
            )
            return edit
        except Exception as exc:
            last_error = str(exc)
            log.warning(
                "parse_edit_validation_error",
                attempt=attempt + 1,
                error=last_error,
            )

    raise GroqParsingError(
        f"No se pudo parsear la instrucción de edición después de "
        f"{max_attempts} intentos. Último error: {last_error}"
    )
