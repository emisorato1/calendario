# src/llm/client.py
"""Cliente LLM con cadena de fallback: Groq → Gemini → OpenAI."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from groq import AsyncGroq

logger = logging.getLogger(__name__)


# ── Respuesta normalizada ─────────────────────────────────────────────────────


@dataclass
class LLMResponse:
    """Respuesta normalizada de cualquier proveedor LLM."""

    content: str
    model: str
    provider: str
    usage: dict | None = None  # {"prompt_tokens": N, "completion_tokens": N}


# ── Protocolo (PEP 544) ──────────────────────────────────────────────────────


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocolo que todo adapter de LLM debe implementar."""

    @property
    def name(self) -> str:
        """Nombre identificador del proveedor (ej: 'groq', 'gemini')."""
        ...

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Envía mensajes al LLM y retorna respuesta normalizada."""
        ...


# ── Adapters ──────────────────────────────────────────────────────────────────


class GroqAdapter:
    """Adapter para Groq API (Llama 3.x)."""

    name = "groq"

    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Envía mensajes a Groq y retorna respuesta normalizada."""
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model=model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
            if response.usage
            else None,
        )


class GeminiAdapter:
    """Adapter para Google Gemini API."""

    name = "gemini"

    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai no está instalado. "
                "Instalalo con: pip install google-generativeai"
            )
        genai.configure(api_key=api_key)
        self._genai = genai

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Envía mensajes a Gemini y retorna respuesta normalizada."""
        gmodel = self._genai.GenerativeModel(model)
        contents = self._convert_messages(messages)
        response = await gmodel.generate_content_async(
            contents,
            generation_config=self._genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return LLMResponse(
            content=response.text,
            model=model,
            provider=self.name,
        )

    @staticmethod
    def _convert_messages(messages: list[dict]) -> list[dict]:
        """Convierte mensajes de formato OpenAI a formato Gemini."""
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [msg["content"]]})
        return contents


class OpenAIAdapter:
    """Adapter para OpenAI API."""

    name = "openai"

    def __init__(self, api_key: str):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "openai no está instalado. Instalalo con: pip install openai"
            )
        self.client = AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Envía mensajes a OpenAI y retorna respuesta normalizada."""
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content,
            model=model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
            if response.usage
            else None,
        )


# ── Proveedor y Cadena de Fallback ────────────────────────────────────────────


@dataclass
class LLMProvider:
    """Configuración de un proveedor LLM dentro de la cadena."""

    adapter: LLMAdapter
    model: str
    timeout: float = 10.0
    max_retries: int = 2


class LLMChain:
    """Cadena de proveedores LLM con fallback automático."""

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Intenta cada proveedor en orden con reintentos y backoff exponencial.

        Args:
            messages: Lista de mensajes en formato OpenAI.
            max_tokens: Máximo de tokens en la respuesta.
            temperature: Temperatura del modelo.

        Returns:
            LLMResponse del primer proveedor que responda.

        Raises:
            RuntimeError: Si todos los proveedores fallan.
        """
        last_error: str | None = None

        for provider in self.providers:
            for attempt in range(provider.max_retries):
                try:
                    response = await asyncio.wait_for(
                        provider.adapter.complete(
                            messages=messages,
                            model=provider.model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=provider.timeout,
                    )
                    logger.info(
                        "LLM response from %s/%s (attempt %d)",
                        provider.adapter.name,
                        provider.model,
                        attempt + 1,
                    )
                    return response

                except asyncio.TimeoutError:
                    logger.warning(
                        "Timeout en %s (attempt %d)",
                        provider.adapter.name,
                        attempt + 1,
                    )
                    last_error = f"Timeout en {provider.adapter.name}"

                except Exception as e:
                    logger.warning(
                        "Error en %s: %s (attempt %d)",
                        provider.adapter.name,
                        e,
                        attempt + 1,
                    )
                    last_error = str(e)

                # Backoff exponencial entre reintentos (1s, 2s, 4s...)
                if attempt < provider.max_retries - 1:
                    await asyncio.sleep(2**attempt)

        # Todos los proveedores fallaron
        logger.error("Todos los LLM fallaron. Último error: %s", last_error)
        raise RuntimeError(f"No se pudo obtener respuesta de ningún LLM: {last_error}")


# ── Factory ───────────────────────────────────────────────────────────────────


def build_llm_chain() -> LLMChain:
    """Construye la cadena de LLM a partir de la configuración.

    Returns:
        LLMChain configurada con los proveedores disponibles.
    """
    from src.config import get_settings

    settings = get_settings()
    providers: list[LLMProvider] = []

    # Siempre: Groq primary + fallback
    groq = GroqAdapter(api_key=settings.groq_api_key)
    providers.append(LLMProvider(adapter=groq, model=settings.groq_model_primary))
    providers.append(LLMProvider(adapter=groq, model=settings.groq_model_fallback))

    # Opcional: Gemini (si la API key está configurada)
    gemini_key = getattr(settings, "gemini_api_key", None)
    if gemini_key:
        try:
            gemini = GeminiAdapter(api_key=gemini_key)
            providers.append(LLMProvider(adapter=gemini, model="gemini-1.5-flash"))
        except ImportError:
            logger.warning("google-generativeai no instalado, Gemini deshabilitado")

    # Opcional: OpenAI (si la API key está configurada)
    openai_key = getattr(settings, "openai_api_key", None)
    if openai_key:
        try:
            openai_adapter = OpenAIAdapter(api_key=openai_key)
            providers.append(LLMProvider(adapter=openai_adapter, model="gpt-4o-mini"))
        except ImportError:
            logger.warning("openai no instalado, OpenAI deshabilitado")

    return LLMChain(providers=providers)
