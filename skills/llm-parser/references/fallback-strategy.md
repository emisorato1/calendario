# Estrategia de Fallback LLM

## Principio

Nunca depender de un solo proveedor de LLM. Implementar una cadena de fallback
para garantizar disponibilidad.

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

## Implementación

```python
from dataclasses import dataclass
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    name: str
    client: object  # Cliente de la API
    model: str
    timeout: float = 10.0
    max_retries: int = 2


class LLMChain:
    """Cadena de proveedores LLM con fallback automático."""

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    async def complete(self, messages: list[dict]) -> str:
        last_error = None

        for provider in self.providers:
            for attempt in range(provider.max_retries):
                try:
                    response = await asyncio.wait_for(
                        provider.client.chat(
                            model=provider.model,
                            messages=messages,
                        ),
                        timeout=provider.timeout,
                    )
                    logger.info(f"LLM response from {provider.name} (attempt {attempt + 1})")
                    return response.content

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout en {provider.name} (attempt {attempt + 1})")
                    last_error = f"Timeout en {provider.name}"

                except Exception as e:
                    logger.warning(f"Error en {provider.name}: {e} (attempt {attempt + 1})")
                    last_error = str(e)

                # Backoff exponencial entre reintentos
                if attempt < provider.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        # Todos los proveedores fallaron
        logger.error(f"Todos los LLM fallaron. Último error: {last_error}")
        raise RuntimeError(f"No se pudo obtener respuesta de ningún LLM: {last_error}")
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
