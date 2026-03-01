"""Tests para agents/calendar_sync/event_builder.py."""

from __future__ import annotations

from datetime import date, time, datetime, timedelta

import pytz
import pytest

from agents.calendar_sync.event_builder import build_event, build_patch, _parse_datetime
from agents.db_manager.models import Cliente
from agents.groq_parser.schemas import EditInstruction, ParsedMessage, TipoServicio
from config.constants import TIMEZONE

tz = pytz.timezone(TIMEZONE)


@pytest.fixture
def cliente_garcia():
    """Cliente de prueba con todos los datos."""
    return Cliente(
        id_cliente=1,
        nombre_completo="García, Juan",
        alias="Juan",
        telefono="2604567890",
        direccion="Av. San Martín 456",
        ciudad="San Rafael",
    )


@pytest.fixture
def cliente_sin_datos():
    """Cliente con datos mínimos."""
    return Cliente(
        nombre_completo="López, Pedro",
    )


@pytest.fixture
def parsed_agendar():
    """ParsedMessage para agendar instalación."""
    return ParsedMessage(
        intencion="agendar",
        nombre_cliente="García",
        tipo_servicio=TipoServicio.instalacion,
        fecha=date(2026, 3, 3),
        hora=time(10, 0),
        duracion_estimada_horas=3.0,
        direccion="Calle Falsa 123",
        telefono="2601234567",
    )


@pytest.fixture
def evento_actual():
    """Evento actual de Google Calendar para tests de build_patch."""
    return {
        "id": "evt_test_1",
        "summary": "García, Juan - 2604567890",
        "start": {"dateTime": "2026-03-03T10:00:00-03:00"},
        "end": {"dateTime": "2026-03-03T13:00:00-03:00"},
        "location": "Av. San Martín 456",
        "colorId": "9",
        "description": "Tipo de Servicio: Instalacion\n---\nNotas: Creado vía IA",
    }


class TestBuildEvent:
    """Tests para build_event."""

    def test_genera_dict_valido_para_api(self, parsed_agendar, cliente_garcia):
        """build_event genera un dict con todos los campos requeridos por la API."""
        result = build_event(parsed_agendar, cliente_garcia)

        assert "summary" in result
        assert "location" in result
        assert "description" in result
        assert "start" in result
        assert "end" in result
        assert "colorId" in result
        assert result["start"]["timeZone"] == TIMEZONE
        assert result["end"]["timeZone"] == TIMEZONE

    def test_prioriza_datos_db_sobre_mensaje(self, parsed_agendar, cliente_garcia):
        """El nombre y teléfono del cliente en DB tienen prioridad sobre el mensaje."""
        result = build_event(parsed_agendar, cliente_garcia)

        # DB tiene "García, Juan" y "2604567890"
        assert result["summary"] == "García, Juan - 2604567890"
        # DB tiene "Av. San Martín 456"
        assert result["location"] == "Av. San Martín 456"

    def test_usa_datos_mensaje_cuando_db_vacia(self, parsed_agendar, cliente_sin_datos):
        """Si el cliente no tiene datos en DB, usa los del mensaje."""
        result = build_event(parsed_agendar, cliente_sin_datos)

        # Cliente sin teléfono ni dirección en DB → usa datos del mensaje
        assert "2601234567" in result["summary"]
        assert result["location"] == "Calle Falsa 123"

    def test_color_correcto_instalacion(self, parsed_agendar, cliente_garcia):
        """Instalación debe tener colorId '9' (Azul)."""
        result = build_event(parsed_agendar, cliente_garcia)
        assert result["colorId"] == "9"

    def test_color_correcto_revision(self, cliente_garcia):
        """Revisión debe tener colorId '5' (Amarillo)."""
        data = ParsedMessage(
            intencion="agendar",
            nombre_cliente="García",
            tipo_servicio=TipoServicio.revision,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
        )
        result = build_event(data, cliente_garcia)
        assert result["colorId"] == "5"

    def test_color_correcto_reparacion(self, cliente_garcia):
        """Reparación debe tener colorId '6' (Naranja)."""
        data = ParsedMessage(
            intencion="agendar",
            nombre_cliente="García",
            tipo_servicio=TipoServicio.reparacion,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
        )
        result = build_event(data, cliente_garcia)
        assert result["colorId"] == "6"

    def test_timezone_aplicado_correctamente(self, parsed_agendar, cliente_garcia):
        """El start/end deben tener timezone de Buenos Aires (-03:00)."""
        result = build_event(parsed_agendar, cliente_garcia)

        start_str = result["start"]["dateTime"]
        assert "-03:00" in start_str

    def test_duracion_correcta(self, parsed_agendar, cliente_garcia):
        """La diferencia entre start y end debe ser la duración del servicio."""
        result = build_event(parsed_agendar, cliente_garcia)

        start = datetime.fromisoformat(result["start"]["dateTime"])
        end = datetime.fromisoformat(result["end"]["dateTime"])
        assert (end - start) == timedelta(hours=3)

    def test_descripcion_formato_estandar(self, parsed_agendar, cliente_garcia):
        """La descripción debe tener el formato estándar con tipo de servicio."""
        result = build_event(parsed_agendar, cliente_garcia)

        desc = result["description"]
        assert "Tipo de Servicio: Instalacion" in desc
        assert "Notas: Creado vía IA" in desc
        assert "Descripción del trabajo:" in desc
        assert "Resultados:" in desc
        assert "Materiales/Equipos utilizados:" in desc
        assert "Códigos de cámaras/alarmas:" in desc

    def test_sin_fecha_lanza_value_error(self, cliente_garcia):
        """Si no hay fecha, debe lanzar ValueError."""
        data = ParsedMessage(
            intencion="agendar",
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=None,
            hora=time(10, 0),
        )
        with pytest.raises(ValueError, match="fecha y hora son requeridos"):
            build_event(data, cliente_garcia)

    def test_sin_hora_lanza_value_error(self, cliente_garcia):
        """Si no hay hora, debe lanzar ValueError."""
        data = ParsedMessage(
            intencion="agendar",
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=date(2026, 3, 3),
            hora=None,
        )
        with pytest.raises(ValueError, match="fecha y hora son requeridos"):
            build_event(data, cliente_garcia)

    def test_titulo_sin_telefono(self, cliente_sin_datos):
        """Si no hay teléfono, el título solo tiene el nombre."""
        data = ParsedMessage(
            intencion="agendar",
            nombre_cliente="López",
            tipo_servicio=TipoServicio.otro,
            fecha=date(2026, 3, 3),
            hora=time(10, 0),
        )
        result = build_event(data, cliente_sin_datos)
        assert result["summary"] == "López, Pedro"


class TestBuildPatch:
    """Tests para build_patch."""

    def test_solo_incluye_campos_con_valor(self, evento_actual, cliente_garcia):
        """build_patch solo incluye en el dict los campos que tienen valor."""
        instruccion = EditInstruction(nueva_fecha=date(2026, 3, 6))
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        assert "start" in patch
        assert "end" in patch
        # No debería incluir campos no modificados
        assert "summary" not in patch
        assert "location" not in patch
        assert "colorId" not in patch

    def test_recalcula_color_si_cambia_tipo(self, evento_actual, cliente_garcia):
        """Si cambia el tipo de servicio, se recalcula el colorId."""
        instruccion = EditInstruction(nuevo_tipo_servicio=TipoServicio.revision)
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        assert patch["colorId"] == "5"  # Revisión = Amarillo

    def test_cambia_fecha_mantiene_hora(self, evento_actual, cliente_garcia):
        """Si solo cambia la fecha, la hora se mantiene."""
        instruccion = EditInstruction(nueva_fecha=date(2026, 3, 6))
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        start = datetime.fromisoformat(patch["start"]["dateTime"])
        assert start.hour == 10
        assert start.minute == 0

    def test_cambia_hora_mantiene_fecha(self, evento_actual, cliente_garcia):
        """Si solo cambia la hora, la fecha se mantiene."""
        instruccion = EditInstruction(nueva_hora=time(15, 0))
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        start = datetime.fromisoformat(patch["start"]["dateTime"])
        assert start.date() == date(2026, 3, 3)
        assert start.hour == 15

    def test_cambia_direccion(self, evento_actual, cliente_garcia):
        """Si cambia la dirección, se incluye en el patch."""
        instruccion = EditInstruction(nueva_direccion="Calle Nueva 789")
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        assert patch["location"] == "Calle Nueva 789"
        assert "start" not in patch

    def test_cambia_telefono_recalcula_titulo(self, evento_actual, cliente_garcia):
        """Si cambia el teléfono, se recalcula el título."""
        instruccion = EditInstruction(nuevo_telefono="2609999999")
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        assert patch["summary"] == "García, Juan - 2609999999"

    def test_cambia_duracion_mantiene_start(self, evento_actual, cliente_garcia):
        """Si solo cambia la duración, el start se mantiene y el end se recalcula."""
        instruccion = EditInstruction(nueva_duracion_horas=2.0)
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        start = datetime.fromisoformat(patch["start"]["dateTime"])
        end = datetime.fromisoformat(patch["end"]["dateTime"])
        assert (end - start) == timedelta(hours=2)

    def test_cambia_fecha_y_duracion(self, evento_actual, cliente_garcia):
        """Si cambian fecha y duración, ambos se recalculan."""
        instruccion = EditInstruction(
            nueva_fecha=date(2026, 3, 10),
            nueva_duracion_horas=4.0,
        )
        patch = build_patch(instruccion, evento_actual, cliente_garcia)

        start = datetime.fromisoformat(patch["start"]["dateTime"])
        end = datetime.fromisoformat(patch["end"]["dateTime"])
        assert start.date() == date(2026, 3, 10)
        assert (end - start) == timedelta(hours=4)


class TestParseDatetime:
    """Tests para la función auxiliar _parse_datetime."""

    def test_parsea_iso_con_offset(self):
        """Parsea correctamente un string ISO 8601 con offset."""
        result = _parse_datetime("2026-03-03T10:00:00-03:00")
        assert result.hour == 10
        assert result.year == 2026

    def test_parsea_iso_sin_timezone_agrega_tz(self):
        """Si el datetime no tiene timezone, lo localiza."""
        result = _parse_datetime("2026-03-03T10:00:00")
        assert result.tzinfo is not None
