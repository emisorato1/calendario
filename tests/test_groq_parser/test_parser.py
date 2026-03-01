"""Tests del parser: parse_message y parse_edit_instruction."""
from __future__ import annotations

from datetime import date, time, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from agents.groq_parser.client import GroqClient
from agents.groq_parser.parser import parse_edit_instruction, parse_message
from agents.groq_parser.schemas import Intencion, TipoServicio
from core.exceptions import GroqParsingError


# ── Helpers ──────────────────────────────────────────────────────────────────


def _future_date(days: int = 3) -> date:
    """Retorna una fecha futura segura para tests."""
    return date.today() + timedelta(days=days)


def _future_date_str(days: int = 3) -> str:
    """Retorna fecha futura como string ISO."""
    return _future_date(days).isoformat()


def _make_mock_client(return_value: dict) -> GroqClient:
    """Crea un GroqClient mock que retorna el dict dado."""
    client = GroqClient.__new__(GroqClient)
    client.call = AsyncMock(return_value=return_value)
    return client


# ── parse_message — Happy paths ──────────────────────────────────────────────


class TestParseMessageExitoso:
    """Tests de parse_message con respuestas válidas."""

    async def test_intencion_agendar(self):
        """Respuesta con intención agendar se parsea correctamente."""
        client = _make_mock_client({
            "intencion": "agendar",
            "nombre_cliente": "García",
            "tipo_servicio": "instalacion",
            "fecha": _future_date_str(),
            "hora": "10:00",
            "duracion_estimada_horas": 3.0,
            "direccion": "Av. San Martín 456",
            "telefono": "2604567890",
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Agendame instalación en lo de García",
            client,
            fecha_actual=_future_date(0),
        )

        assert result.intencion == Intencion.agendar
        assert result.nombre_cliente == "García"
        assert result.tipo_servicio == TipoServicio.instalacion
        assert result.duracion_estimada_horas == 3.0

    async def test_intencion_cancelar(self):
        """Respuesta con intención cancelar."""
        client = _make_mock_client({
            "intencion": "cancelar",
            "nombre_cliente": "Pérez",
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Cancelá lo de Pérez", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.cancelar
        assert result.nombre_cliente == "Pérez"

    async def test_intencion_editar(self):
        """Respuesta con intención editar."""
        client = _make_mock_client({
            "intencion": "editar",
            "nombre_cliente": "López",
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Editá el turno de López", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.editar
        assert result.nombre_cliente == "López"

    async def test_intencion_listar_pendientes(self):
        """Respuesta con intención listar_pendientes."""
        client = _make_mock_client({
            "intencion": "listar_pendientes",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Qué tengo pendiente?", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.listar_pendientes

    async def test_intencion_listar_historial(self):
        """Respuesta con intención listar_historial."""
        client = _make_mock_client({
            "intencion": "listar_historial",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Qué hice la semana pasada?", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.listar_historial

    async def test_intencion_listar_dia(self):
        """Respuesta con intención listar_dia y fecha_consulta."""
        next_date = _future_date(1)
        client = _make_mock_client({
            "intencion": "listar_dia",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": next_date.isoformat(),
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Qué tengo para el lunes?", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.listar_dia
        assert result.fecha_consulta == next_date

    async def test_intencion_listar_cliente(self):
        """Respuesta con intención listar_cliente."""
        client = _make_mock_client({
            "intencion": "listar_cliente",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": "Juan",
            "urgente": False,
        })

        result = await parse_message(
            "Cuándo tengo que ir a lo de Juan?", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.listar_cliente
        assert result.cliente_consulta == "Juan"

    async def test_intencion_otro(self):
        """Respuesta con intención otro."""
        client = _make_mock_client({
            "intencion": "otro",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Hola", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.otro

    async def test_urgente_detectado(self):
        """Campo urgente=True se propaga correctamente."""
        client = _make_mock_client({
            "intencion": "agendar",
            "nombre_cliente": "García",
            "tipo_servicio": "instalacion",
            "fecha": _future_date_str(),
            "hora": "10:00",
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": True,
        })

        result = await parse_message(
            "Es urgente, agendame instalación",
            client,
            fecha_actual=_future_date(0),
        )

        assert result.urgente is True

    async def test_duracion_inferida_automaticamente(self):
        """Si el LLM no retorna duración pero sí tipo, se infiere."""
        client = _make_mock_client({
            "intencion": "agendar",
            "nombre_cliente": "Test",
            "tipo_servicio": "revision",
            "fecha": _future_date_str(),
            "hora": "15:00",
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        })

        result = await parse_message(
            "Revisión en lo de Test", client, fecha_actual=_future_date(0)
        )

        assert result.duracion_estimada_horas == 1.0


# ── parse_message — Errores y reintentos ─────────────────────────────────────


class TestParseMessageErrores:
    """Tests de error handling y reintentos de parse_message."""

    async def test_json_invalido_reintenta_y_falla(self):
        """LLM retorna datos inválidos 3 veces → GroqParsingError."""
        # Siempre retorna un dict que no es un intencion válida
        client = _make_mock_client({
            "intencion": "no_existe",
        })

        with pytest.raises(GroqParsingError, match="3 intentos"):
            await parse_message(
                "Algo raro", client, fecha_actual=_future_date(0)
            )

        # Se llamó 3 veces (1 + 2 reintentos)
        assert client.call.call_count == 3

    async def test_reintento_exitoso_en_segundo_intento(self):
        """Primer intento falla validación, segundo OK."""
        valid_response = {
            "intencion": "agendar",
            "nombre_cliente": "Test",
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        }

        client = GroqClient.__new__(GroqClient)
        client.call = AsyncMock(side_effect=[
            {"intencion": "INVALIDO"},  # Falla validación
            valid_response,             # Éxito
        ])

        result = await parse_message(
            "Test", client, fecha_actual=_future_date(0)
        )

        assert result.intencion == Intencion.agendar
        assert client.call.call_count == 2

    async def test_prompt_de_reintento_incluye_error(self):
        """En el reintento, el prompt incluye el error anterior."""
        valid_response = {
            "intencion": "otro",
            "nombre_cliente": None,
            "tipo_servicio": None,
            "fecha": None,
            "hora": None,
            "duracion_estimada_horas": None,
            "direccion": None,
            "telefono": None,
            "fecha_consulta": None,
            "cliente_consulta": None,
            "urgente": False,
        }

        client = GroqClient.__new__(GroqClient)
        client.call = AsyncMock(side_effect=[
            {"intencion": "X"},  # Error: no existe en enum
            valid_response,
        ])

        await parse_message("test", client, fecha_actual=_future_date(0))

        # El segundo call debe incluir el error en el user_prompt
        second_call = client.call.call_args_list[1]
        user_prompt = second_call.kwargs.get("user_prompt", second_call.args[1] if len(second_call.args) > 1 else "")
        assert "ERROR EN INTENTO ANTERIOR" in user_prompt


# ── parse_edit_instruction ───────────────────────────────────────────────────


class TestParseEditInstruction:
    """Tests de parse_edit_instruction."""

    async def test_edicion_fecha_hora(self):
        """Instrucción de cambio de fecha y hora."""
        new_date = _future_date(5)
        client = _make_mock_client({
            "nueva_fecha": new_date.isoformat(),
            "nueva_hora": "16:00",
            "nuevo_tipo_servicio": None,
            "nueva_direccion": None,
            "nuevo_telefono": None,
            "nueva_duracion_horas": None,
        })

        evento = {
            "summary": "García - 260-111",
            "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
        }

        result = await parse_edit_instruction(
            instruccion="Pasalo para el viernes a las 16",
            evento_actual=evento,
            client=client,
            fecha_actual=_future_date(0),
        )

        assert result.nueva_fecha == new_date
        assert result.nueva_hora == time(16, 0)
        assert result.nuevo_tipo_servicio is None

    async def test_edicion_tipo_servicio(self):
        """Instrucción de cambio de tipo de servicio."""
        client = _make_mock_client({
            "nueva_fecha": None,
            "nueva_hora": None,
            "nuevo_tipo_servicio": "instalacion",
            "nueva_direccion": None,
            "nuevo_telefono": None,
            "nueva_duracion_horas": None,
        })

        evento = {"summary": "Test", "description": "Tipo: revision"}

        result = await parse_edit_instruction(
            instruccion="Cambiá el servicio a instalación de cámaras",
            evento_actual=evento,
            client=client,
            fecha_actual=_future_date(0),
        )

        assert result.nuevo_tipo_servicio == TipoServicio.instalacion
        assert result.nueva_fecha is None

    async def test_edicion_direccion(self):
        """Instrucción de cambio de dirección."""
        client = _make_mock_client({
            "nueva_fecha": None,
            "nueva_hora": None,
            "nuevo_tipo_servicio": None,
            "nueva_direccion": "Calle Nueva 789",
            "nuevo_telefono": None,
            "nueva_duracion_horas": None,
        })

        result = await parse_edit_instruction(
            instruccion="Cambiá la dirección a Calle Nueva 789",
            evento_actual={"summary": "Test"},
            client=client,
            fecha_actual=_future_date(0),
        )

        assert result.nueva_direccion == "Calle Nueva 789"

    async def test_edicion_multiples_campos(self):
        """Instrucción con múltiples cambios."""
        new_date = _future_date(7)
        client = _make_mock_client({
            "nueva_fecha": new_date.isoformat(),
            "nueva_hora": "09:00",
            "nuevo_tipo_servicio": "reparacion",
            "nueva_direccion": None,
            "nuevo_telefono": None,
            "nueva_duracion_horas": 2.0,
        })

        result = await parse_edit_instruction(
            instruccion="Pasalo al lunes a las 9, que sea reparación de 2 horas",
            evento_actual={"summary": "Test"},
            client=client,
            fecha_actual=_future_date(0),
        )

        assert result.nueva_fecha == new_date
        assert result.nueva_hora == time(9, 0)
        assert result.nuevo_tipo_servicio == TipoServicio.reparacion
        assert result.nueva_duracion_horas == 2.0

    async def test_edicion_invalida_3_veces_lanza_error(self):
        """3 intentos inválidos → GroqParsingError."""
        # Siempre retorna todo None → EditInstruction falla
        client = _make_mock_client({
            "nueva_fecha": None,
            "nueva_hora": None,
            "nuevo_tipo_servicio": None,
            "nueva_direccion": None,
            "nuevo_telefono": None,
            "nueva_duracion_horas": None,
        })

        with pytest.raises(GroqParsingError, match="3 intentos"):
            await parse_edit_instruction(
                instruccion="No sé qué quiero cambiar",
                evento_actual={"summary": "Test"},
                client=client,
                fecha_actual=_future_date(0),
            )

        assert client.call.call_count == 3
