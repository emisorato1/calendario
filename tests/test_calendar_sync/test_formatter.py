"""Tests para agents/calendar_sync/formatter.py."""

from __future__ import annotations

import pytest

from agents.calendar_sync.formatter import (
    format_event_list_item,
    format_event_summary,
    format_events_list,
    _extract_tipo_servicio,
    _color_nombre,
    _parse_dt,
)


@pytest.fixture
def evento_completo():
    """Evento de Google Calendar con todos los campos."""
    return {
        "id": "evt_test_1",
        "summary": "García, Juan - 2604567890",
        "start": {"dateTime": "2026-03-03T10:00:00-03:00"},
        "end": {"dateTime": "2026-03-03T13:00:00-03:00"},
        "location": "Av. San Martín 456",
        "colorId": "9",
        "description": "Tipo de Servicio: Instalacion\n---\nNotas: Creado vía IA",
    }


@pytest.fixture
def evento_revision():
    """Evento de revisión."""
    return {
        "id": "evt_test_2",
        "summary": "López, Pedro - 2601111111",
        "start": {"dateTime": "2026-03-02T09:00:00-03:00"},
        "end": {"dateTime": "2026-03-02T10:00:00-03:00"},
        "location": "Calle Falsa 123",
        "colorId": "5",
        "description": "Tipo de Servicio: Revision\n---\nNotas: Creado vía IA",
    }


@pytest.fixture
def evento_sin_descripcion():
    """Evento sin campo description."""
    return {
        "id": "evt_test_3",
        "summary": "Test",
        "start": {"dateTime": "2026-03-04T14:00:00-03:00"},
        "end": {"dateTime": "2026-03-04T15:00:00-03:00"},
        "colorId": "8",
        "description": "",
    }


class TestFormatEventSummary:
    """Tests para format_event_summary."""

    def test_produce_texto_esperado(self, evento_completo):
        """Verifica que el resumen contiene todos los campos formateados."""
        result = format_event_summary(evento_completo)

        assert "Instalacion" in result
        assert "García, Juan" in result
        assert "Martes" in result
        assert "03/03/2026" in result
        assert "10:00" in result
        assert "13:00" in result
        assert "3h" in result
        assert "Av. San Martín 456" in result
        assert "🔵" in result
        assert "Azul" in result

    def test_evento_sin_ubicacion(self, evento_completo):
        """Si no tiene location, muestra 'No especificada'."""
        del evento_completo["location"]
        result = format_event_summary(evento_completo)
        assert "No especificada" in result

    def test_contiene_emojis_de_seccion(self, evento_completo):
        """El resumen debe contener los emojis de cada sección."""
        result = format_event_summary(evento_completo)

        assert "\U0001f527" in result  # 🔧 Tipo
        assert "\U0001f464" in result  # 👤 Cliente
        assert "\U0001f4c5" in result  # 📅 Fecha
        assert "\U0001f550" in result  # 🕐 Hora
        assert "\U0001f4cd" in result  # 📍 Dirección
        assert "\U0001f3a8" in result  # 🎨 Color


class TestFormatEventListItem:
    """Tests para format_event_list_item."""

    def test_formato_correcto_con_indice(self, evento_completo):
        """Genera texto con número emoji, fecha, hora, color y tipo."""
        result = format_event_list_item(evento_completo, 1)

        assert "1\ufe0f\u20e3" in result  # 1️⃣
        assert "Mar" in result  # Martes abreviado
        assert "03/03" in result
        assert "10:00" in result
        assert "13:00" in result
        assert "🔵" in result
        assert "Instalacion" in result
        assert "García, Juan" in result

    def test_formato_con_indice_2(self, evento_revision):
        """Verifica formato con índice 2."""
        result = format_event_list_item(evento_revision, 2)

        assert "2\ufe0f\u20e3" in result
        assert "Lun" in result
        assert "🟡" in result
        assert "Revision" in result
        assert "López, Pedro" in result

    def test_indice_mayor_a_10_usa_numero(self):
        """Índice > 10 usa formato numérico simple."""
        evento = {
            "id": "evt_11",
            "summary": "Test - 123",
            "start": {"dateTime": "2026-03-03T10:00:00-03:00"},
            "end": {"dateTime": "2026-03-03T11:00:00-03:00"},
            "colorId": "8",
            "description": "Tipo de Servicio: Otro",
        }
        result = format_event_list_item(evento, 11)
        assert "11." in result

    def test_evento_sin_tipo_muestra_sin_tipo(self, evento_sin_descripcion):
        """Evento sin tipo en descripción muestra 'Sin tipo'."""
        result = format_event_list_item(evento_sin_descripcion, 1)
        assert "Sin tipo" in result


class TestFormatEventsList:
    """Tests para format_events_list."""

    def test_lista_con_eventos(self, evento_completo, evento_revision):
        """Lista con eventos formatea correctamente con header y conteo."""
        result = format_events_list(
            [evento_completo, evento_revision],
            "Eventos pendientes",
        )

        assert "Eventos pendientes (2):" in result
        assert "📌" in result

    def test_lista_vacia_mensaje_apropiado(self):
        """Lista vacía devuelve mensaje de 'No hay eventos'."""
        result = format_events_list([], "Eventos pendientes")

        assert "No hay eventos programados" in result
        assert "Eventos pendientes" in result

    def test_lista_con_un_evento(self, evento_completo):
        """Lista con un solo evento."""
        result = format_events_list([evento_completo], "Próximos eventos")

        assert "Próximos eventos (1):" in result


class TestExtractTipoServicio:
    """Tests para _extract_tipo_servicio."""

    def test_extrae_tipo_correctamente(self):
        """Extrae el tipo desde una descripción estándar."""
        desc = "Tipo de Servicio: Instalacion\n---\nNotas: Creado vía IA"
        assert _extract_tipo_servicio(desc) == "Instalacion"

    def test_sin_tipo_retorna_sin_tipo(self):
        """Si no hay tipo, retorna 'Sin tipo'."""
        assert _extract_tipo_servicio("") == "Sin tipo"
        assert _extract_tipo_servicio("Notas: algo") == "Sin tipo"


class TestColorNombre:
    """Tests para _color_nombre."""

    def test_color_conocido(self):
        """Colores conocidos retornan nombre correcto."""
        assert _color_nombre("9") == "Azul"
        assert _color_nombre("6") == "Naranja"
        assert _color_nombre("5") == "Amarillo"
        assert _color_nombre("8") == "Grafito"

    def test_color_desconocido(self):
        """Color desconocido retorna 'Desconocido'."""
        assert _color_nombre("99") == "Desconocido"


class TestParseDt:
    """Tests para _parse_dt."""

    def test_string_valido(self):
        """Parsea un string ISO 8601 válido."""
        result = _parse_dt("2026-03-03T10:00:00-03:00")
        assert result is not None
        assert result.hour == 10

    def test_string_vacio_retorna_none(self):
        """String vacío retorna None."""
        assert _parse_dt("") is None
