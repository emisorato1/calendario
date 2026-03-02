# src/llm/parser.py
"""Parser LLM: interpreta mensajes de usuario y extrae datos estructurados."""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel

from src.core.exceptions import LLMParsingError, LLMUnavailableError
from src.db.models import Evento
from src.llm.client import LLMChain
from src.llm.prompts import (
    STATIC_FALLBACK,
    format_closure_prompt,
    format_create_event_prompt,
    format_edit_event_prompt,
    format_intent_detection_prompt,
    format_system_prompt,
)
from src.llm.schemas import (
    IntentDetection,
    ParsedClosure,
    ParsedEdit,
    ParsedEvent,
    parse_llm_response,
)

logger = logging.getLogger(__name__)

# Máximo de reintentos por validación fallida de JSON
_MAX_PARSE_RETRIES = 2


class LLMParser:
    """Clase principal que usa LLMChain y prompts para interpretar mensajes."""

    def __init__(self, chain: LLMChain):
        self._chain = chain

    async def detect_intent(self, text: str) -> IntentDetection:
        """Detecta la intención del usuario a partir de texto libre.

        Args:
            text: Mensaje del usuario.

        Returns:
            IntentDetection con la intención y datos extraídos.

        Raises:
            LLMUnavailableError: Si todos los proveedores LLM fallan.
            LLMParsingError: Si la respuesta no se puede parsear tras reintentos.
        """
        user_prompt = format_intent_detection_prompt(text)
        return await self._call_and_parse(user_prompt, IntentDetection)

    async def parse_create_event(self, text: str) -> ParsedEvent:
        """Extrae datos de un evento a crear desde texto libre.

        Args:
            text: Mensaje del usuario describiendo el evento.

        Returns:
            ParsedEvent con los datos extraídos y campos faltantes.

        Raises:
            LLMUnavailableError: Si todos los proveedores LLM fallan.
            LLMParsingError: Si la respuesta no se puede parsear tras reintentos.
        """
        user_prompt = format_create_event_prompt(text)
        return await self._call_and_parse(user_prompt, ParsedEvent)

    async def parse_edit_event(self, text: str, current_event: Evento) -> ParsedEdit:
        """Identifica qué campos del evento modificar.

        Args:
            text: Mensaje del usuario con los cambios deseados.
            current_event: Evento actual con sus datos.

        Returns:
            ParsedEdit con los cambios a aplicar.

        Raises:
            LLMUnavailableError: Si todos los proveedores LLM fallan.
            LLMParsingError: Si la respuesta no se puede parsear tras reintentos.
        """
        user_prompt = format_edit_event_prompt(current_event, text)
        return await self._call_and_parse(user_prompt, ParsedEdit)

    async def parse_closure(self, text: str) -> ParsedClosure:
        """Extrae datos del cierre de un servicio.

        Args:
            text: Mensaje del usuario con los datos de cierre.

        Returns:
            ParsedClosure con trabajo realizado, monto, notas.

        Raises:
            LLMUnavailableError: Si todos los proveedores LLM fallan.
            LLMParsingError: Si la respuesta no se puede parsear tras reintentos.
        """
        user_prompt = format_closure_prompt(text)
        return await self._call_and_parse(user_prompt, ParsedClosure)

    async def _call_and_parse(
        self, user_prompt: str, schema_class: type[BaseModel]
    ) -> BaseModel:
        """Llama al LLM y parsea la respuesta contra un schema Pydantic.

        Reintenta si la respuesta JSON es inválida (máximo _MAX_PARSE_RETRIES).

        Args:
            user_prompt: Prompt del usuario formateado.
            schema_class: Clase Pydantic para validar la respuesta.

        Returns:
            Instancia validada del schema.

        Raises:
            LLMUnavailableError: Si la cadena LLM no puede responder.
            LLMParsingError: Si la respuesta no se puede parsear tras reintentos.
        """
        system_prompt = format_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Optional[str] = None

        for attempt in range(_MAX_PARSE_RETRIES):
            # Intentar obtener respuesta del LLM
            try:
                response = await self._chain.complete(messages=messages)
            except RuntimeError as e:
                logger.error("Cadena LLM falló completamente: %s", e)
                raise LLMUnavailableError(
                    STATIC_FALLBACK,
                    details=str(e),
                )

            # Intentar parsear la respuesta
            raw_content = response.content
            try:
                # Extraer JSON del contenido (a veces el LLM envuelve en markdown)
                json_str = self._extract_json(raw_content)
                result = parse_llm_response(json_str, schema_class)
                logger.debug(
                    "Respuesta parseada exitosamente con %s/%s (intento %d)",
                    response.provider,
                    response.model,
                    attempt + 1,
                )
                return result
            except ValueError as e:
                last_error = str(e)
                logger.warning(
                    "Error parseando respuesta del LLM (intento %d/%d): %s",
                    attempt + 1,
                    _MAX_PARSE_RETRIES,
                    e,
                )

        # Todos los intentos de parsing fallaron
        raise LLMParsingError(
            "No se pudo parsear la respuesta del LLM",
            details=last_error or "Error desconocido",
        )

    @staticmethod
    def _extract_json(content: str) -> str:
        """Extrae el bloque JSON de la respuesta del LLM.

        Maneja casos donde el LLM envuelve el JSON en bloques ```json...```
        o incluye texto antes/después del JSON.

        Args:
            content: Contenido crudo de la respuesta del LLM.

        Returns:
            String JSON limpio.
        """
        # Caso 1: Bloque markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Caso 2: JSON directo — buscar primer { hasta último }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start : end + 1]

        # Caso 3: Devolver tal cual (dejará que json.loads falle con buen error)
        return content.strip()
