# Estrategia de Fallback LLM

## Principio

Nunca depender de un solo proveedor de LLM. Implementar una cadena de fallback
para garantizar disponibilidad. Cada proveedor se conecta a través de un
**adapter** con interfaz común, lo que permite intercambiarlos sin cambiar el
código del orquestador.

## Cadena de Fallback

```
Groq (Llama 3.3 70B)
    ↓ falla / timeout
Groq (Llama 3.1 8B - modelo rápido)
    ↓ falla / timeout
Gemini Flash (si configurado)
    ↓ falla / timeout
OpenAI GPT-4o-mini (si configurado)
    ↓ falla / timeout
Respuesta de fallback estática
```

## Adapter Pattern — Interfaz Común

Cada proveedor de LLM implementa `LLMAdapter`, un protocolo (duck-typing
estructural) que define el contrato mínimo:

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Respuesta normalizada de cualquier proveedor LLM."""
    content: str
    model: str
    provider: str
    usage: dict | None = None  # {"prompt_tokens": N, "completion_tokens": N}


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
```

### Adapter para Groq

```python
from groq import AsyncGroq


class GroqAdapter:
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
            } if response.usage else None,
        )
```

### Adapter para Gemini

```python
import google.generativeai as genai


class GeminiAdapter:
    name = "gemini"

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
        gmodel = genai.GenerativeModel(model)
        # Convertir formato OpenAI → Gemini
        contents = self._convert_messages(messages)
        response = await gmodel.generate_content_async(
            contents,
            generation_config=genai.types.GenerationConfig(
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
```

### Adapter para OpenAI

```python
from openai import AsyncOpenAI


class OpenAIAdapter:
    name = "openai"

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> LLMResponse:
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
            } if response.usage else None,
        )
```

## Cadena de Fallback con Adapters

```python
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
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
        last_error = None

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
                        f"LLM response from {provider.adapter.name}/{provider.model} "
                        f"(attempt {attempt + 1})"
                    )
                    return response

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout en {provider.adapter.name} (attempt {attempt + 1})"
                    )
                    last_error = f"Timeout en {provider.adapter.name}"

                except Exception as e:
                    logger.warning(
                        f"Error en {provider.adapter.name}: {e} (attempt {attempt + 1})"
                    )
                    last_error = str(e)

                # Backoff exponencial entre reintentos
                if attempt < provider.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        # Todos los proveedores fallaron
        logger.error(f"Todos los LLM fallaron. Último error: {last_error}")
        raise RuntimeError(f"No se pudo obtener respuesta de ningún LLM: {last_error}")
```

## Inicialización de la Cadena

```python
from src.config import get_settings

def build_llm_chain() -> LLMChain:
    """Construye la cadena de LLM a partir de la configuración."""
    settings = get_settings()
    providers: list[LLMProvider] = []

    # Siempre: Groq primary
    groq = GroqAdapter(api_key=settings.groq_api_key)
    providers.append(LLMProvider(adapter=groq, model=settings.groq_model_primary))
    providers.append(LLMProvider(adapter=groq, model=settings.groq_model_fallback))

    # Opcional: Gemini (si la API key está configurada)
    gemini_key = getattr(settings, "gemini_api_key", None)
    if gemini_key:
        gemini = GeminiAdapter(api_key=gemini_key)
        providers.append(LLMProvider(adapter=gemini, model="gemini-1.5-flash"))

    # Opcional: OpenAI (si la API key está configurada)
    openai_key = getattr(settings, "openai_api_key", None)
    if openai_key:
        openai_adapter = OpenAIAdapter(api_key=openai_key)
        providers.append(LLMProvider(adapter=openai_adapter, model="gpt-4o-mini"))

    return LLMChain(providers=providers)
```

## Respuesta de Fallback Estática

Si todos los LLM fallan, el bot no se cuelga. En cambio:

```python
STATIC_FALLBACK = (
    "⚠️ No pude procesar tu mensaje en este momento.\n\n"
    "Intentá de nuevo en unos segundos o usá los botones del menú (/menu) "
    "para realizar la acción que necesitás."
)
```

## Notas

- El timeout debe ser agresivo (10s) para no hacer esperar al usuario.
- Loguear siempre cuál proveedor respondió y cuántos intentos tomó.
- Los proveedores de fallback pueden tener modelos más pequeños (trade-off
  velocidad vs calidad).
- `LLMAdapter` usa `Protocol` (PEP 544): no requiere herencia explícita.
  Cualquier clase que implemente `name` y `complete()` con la firma correcta
  es un adapter válido.
- `LLMResponse` normaliza la respuesta — el orquestador nunca accede a
  objetos crudos de Groq/OpenAI/Gemini.
- Para agregar un nuevo proveedor: crear una clase con `name` y `complete()`,
  luego añadirla a `build_llm_chain()`. No se requiere modificar `LLMChain`.
