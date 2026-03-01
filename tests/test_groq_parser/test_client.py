"""Tests del GroqClient: reintentos, fallback, timeout."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from groq import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel

from agents.groq_parser.client import GroqClient
from core.exceptions import GroqTimeoutError


# ── Helpers ──────────────────────────────────────────────────────────────────


class DummyModel(BaseModel):
    """Modelo dummy para response_format en tests."""
    text: str


def _make_groq_response(content: str) -> MagicMock:
    """Crea un mock de respuesta de Groq con el contenido dado."""
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20

    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_client() -> GroqClient:
    """Crea un GroqClient para tests."""
    return GroqClient(
        api_key="test_key",
        model_primary="model-primary",
        model_fallback="model-fallback",
        timeout=1.0,
    )


# ── Tests de llamada exitosa ─────────────────────────────────────────────────


class TestCallExitosa:
    """Tests de llamada exitosa al LLM."""

    async def test_call_retorna_dict_parseado(self):
        """Respuesta JSON válida se parsea correctamente."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "hola"}')

        with patch.object(
            client.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.call(
                system_prompt="test",
                user_prompt="test",
                response_format=DummyModel,
            )

        assert result == {"text": "hola"}

    async def test_call_usa_modelo_primario(self):
        """La primera llamada usa el modelo primario."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "ok"}')

        with patch.object(
            client.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await client.call(
                system_prompt="sys",
                user_prompt="usr",
                response_format=DummyModel,
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model"] == "model-primary"


# ── Tests de reintentos ──────────────────────────────────────────────────────


class TestReintentos:
    """Tests de retry con tenacity."""

    async def test_timeout_reintenta_y_exito(self):
        """Timeout en primer intento, éxito en segundo."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "ok"}')

        mock_create = AsyncMock(
            side_effect=[
                APITimeoutError(request=MagicMock()),
                mock_response,
            ]
        )

        with patch.object(
            client.client.chat.completions, "create", mock_create
        ):
            result = await client.call(
                system_prompt="sys",
                user_prompt="usr",
                response_format=DummyModel,
            )

        assert result == {"text": "ok"}
        assert mock_create.call_count == 2

    async def test_rate_limit_reintenta_y_exito(self):
        """Rate limit en primer intento, éxito en segundo."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "ok"}')

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}

        mock_create = AsyncMock(
            side_effect=[
                RateLimitError(
                    message="rate limit",
                    response=mock_resp,
                    body=None,
                ),
                mock_response,
            ]
        )

        with patch.object(
            client.client.chat.completions, "create", mock_create
        ):
            result = await client.call(
                system_prompt="sys",
                user_prompt="usr",
                response_format=DummyModel,
            )

        assert result == {"text": "ok"}

    async def test_connection_error_reintenta(self):
        """Connection error en primer intento, éxito en segundo."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "ok"}')

        mock_create = AsyncMock(
            side_effect=[
                APIConnectionError(request=MagicMock()),
                mock_response,
            ]
        )

        with patch.object(
            client.client.chat.completions, "create", mock_create
        ):
            result = await client.call(
                system_prompt="sys",
                user_prompt="usr",
                response_format=DummyModel,
            )

        assert result == {"text": "ok"}


# ── Tests de fallback ────────────────────────────────────────────────────────


class TestFallback:
    """Tests de fallback al modelo secundario."""

    async def test_primario_falla_3_veces_usa_fallback(self):
        """3 fallos del primario → intenta con fallback."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "fallback_ok"}')

        call_count = 0
        call_models = []

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            call_models.append(kwargs.get("model"))

            if kwargs.get("model") == "model-primary":
                raise APITimeoutError(request=MagicMock())
            return mock_response

        with patch.object(
            client.client.chat.completions, "create", side_effect=mock_create
        ):
            result = await client.call(
                system_prompt="sys",
                user_prompt="usr",
                response_format=DummyModel,
            )

        assert result == {"text": "fallback_ok"}
        # 3 intentos primario + al menos 1 intento fallback
        assert "model-primary" in call_models
        assert "model-fallback" in call_models

    async def test_ambos_modelos_fallan_lanza_timeout_error(self):
        """Primario + fallback fallan 3 veces cada uno → GroqTimeoutError."""
        client = _make_client()

        mock_create = AsyncMock(
            side_effect=APITimeoutError(request=MagicMock())
        )

        with patch.object(
            client.client.chat.completions, "create", mock_create
        ):
            with pytest.raises(GroqTimeoutError):
                await client.call(
                    system_prompt="sys",
                    user_prompt="usr",
                    response_format=DummyModel,
                )

        # 3 intentos primario + 3 intentos fallback = 6
        assert mock_create.call_count == 6


# ── Tests de logging ─────────────────────────────────────────────────────────


class TestLogging:
    """Tests de logging del cliente."""

    async def test_call_exitosa_loguea_info(self):
        """Una llamada exitosa genera un log con modelo y tokens."""
        client = _make_client()
        mock_response = _make_groq_response('{"text": "ok"}')

        with patch.object(
            client.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with patch("agents.groq_parser.client.log") as mock_log:
                await client.call(
                    system_prompt="sys",
                    user_prompt="usr",
                    response_format=DummyModel,
                )

                mock_log.info.assert_called()
                call_kwargs = mock_log.info.call_args
                assert call_kwargs.kwargs["model"] == "model-primary"
                assert "tokens_prompt" in call_kwargs.kwargs
                assert "latency_ms" in call_kwargs.kwargs
