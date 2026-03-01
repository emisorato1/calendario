"""Wrapper async sobre Groq SDK con reintentos, fallback y logging."""

from __future__ import annotations

import time as time_module
from typing import Any

from groq import AsyncGroq
from groq import APITimeoutError, APIConnectionError, RateLimitError
from pydantic import BaseModel
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.exceptions import GroqTimeoutError
from core.logger import get_logger

log = get_logger(__name__)


class GroqClient:
    """Cliente async para Groq API con reintentos y fallback de modelo."""

    def __init__(
        self,
        api_key: str,
        model_primary: str = "llama-3.3-70b-versatile",
        model_fallback: str = "llama-3.1-8b-instant",
        max_tokens: int = 512,
        temperature: float = 0.1,
        timeout: float = 10.0,
    ) -> None:
        self.client = AsyncGroq(api_key=api_key, timeout=timeout)
        self.model_primary = model_primary
        self.model_fallback = model_fallback
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: type[BaseModel],
    ) -> dict:
        """Llama al LLM con reintentos y fallback de modelo.

        Args:
            system_prompt: Prompt de sistema.
            user_prompt: Prompt del usuario.
            response_format: Modelo Pydantic para JSON mode.

        Returns:
            Diccionario parseado de la respuesta del LLM.

        Raises:
            GroqTimeoutError: Si todos los intentos (primario + fallback) fallan.
        """
        # Intento con modelo primario
        try:
            return await self._call_with_retries(
                model=self.model_primary,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
            )
        except GroqTimeoutError:
            log.warning(
                "modelo_primario_agotado",
                model=self.model_primary,
                fallback=self.model_fallback,
            )

        # Fallback al modelo secundario
        try:
            return await self._call_with_retries(
                model=self.model_fallback,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
            )
        except GroqTimeoutError:
            log.error(
                "fallback_tambien_agotado",
                model_primary=self.model_primary,
                model_fallback=self.model_fallback,
            )
            raise

    @retry(
        retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    async def _call_single(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format: type[BaseModel],
    ) -> dict:
        """Llamada individual al LLM con decorador de reintentos tenacity."""
        start = time_module.monotonic()

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        latency_ms = (time_module.monotonic() - start) * 1000
        usage = response.usage

        log.info(
            "groq_call_ok",
            model=model,
            tokens_prompt=usage.prompt_tokens if usage else 0,
            tokens_completion=usage.completion_tokens if usage else 0,
            latency_ms=round(latency_ms, 1),
        )

        import json

        content = response.choices[0].message.content
        if content is None:
            raise APIConnectionError(request=None)  # type: ignore[arg-type]
        return json.loads(content)

    async def _call_with_retries(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format: type[BaseModel],
    ) -> dict:
        """Wrapper que convierte excepciones de tenacity a GroqTimeoutError."""
        try:
            return await self._call_single(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
            )
        except RetryError as exc:
            raise GroqTimeoutError(
                f"Groq API falló después de 3 intentos con modelo {model}: {exc}"
            ) from exc
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            raise GroqTimeoutError(
                f"Groq API falló después de 3 intentos con modelo {model}: {exc}"
            ) from exc
