"""Tests para agents/calendar_sync/colors.py."""

from __future__ import annotations

import pytest

from agents.calendar_sync.colors import get_color_emoji, get_color_id
from config.constants import COLOR_EMOJI, COLOR_MAP


class TestGetColorId:
    """Tests para get_color_id."""

    def test_instalacion_retorna_9(self):
        """Instalación debe retornar colorId '9' (Azul)."""
        assert get_color_id("instalacion") == "9"

    def test_revision_retorna_5(self):
        """Revisión debe retornar colorId '5' (Amarillo)."""
        assert get_color_id("revision") == "5"

    def test_reparacion_retorna_6(self):
        """Reparación debe retornar colorId '6' (Naranja)."""
        assert get_color_id("reparacion") == "6"

    def test_mantenimiento_retorna_6(self):
        """Mantenimiento debe retornar colorId '6' (Naranja)."""
        assert get_color_id("mantenimiento") == "6"

    def test_presupuesto_retorna_5(self):
        """Presupuesto debe retornar colorId '5' (Amarillo)."""
        assert get_color_id("presupuesto") == "5"

    def test_otro_retorna_8(self):
        """'otro' debe retornar colorId '8' (Grafito)."""
        assert get_color_id("otro") == "8"

    def test_tipo_desconocido_retorna_default_otro(self):
        """Tipo no reconocido debe retornar el colorId de 'otro'."""
        assert get_color_id("desconocido") == COLOR_MAP["otro"]

    def test_case_insensitive(self):
        """Debe funcionar sin importar mayúsculas/minúsculas."""
        assert get_color_id("Instalacion") == "9"
        assert get_color_id("REVISION") == "5"

    def test_todos_los_tipos_tienen_color(self):
        """Todos los tipos definidos en COLOR_MAP tienen un color asignado."""
        for tipo, color_id in COLOR_MAP.items():
            assert get_color_id(tipo) == color_id


class TestGetColorEmoji:
    """Tests para get_color_emoji."""

    def test_instalacion_retorna_azul(self):
        """Instalación → emoji azul."""
        assert get_color_emoji("instalacion") == "🔵"

    def test_revision_retorna_amarillo(self):
        """Revisión → emoji amarillo."""
        assert get_color_emoji("revision") == "🟡"

    def test_reparacion_retorna_naranja(self):
        """Reparación → emoji naranja."""
        assert get_color_emoji("reparacion") == "🟠"

    def test_otro_retorna_negro(self):
        """'otro' → emoji negro."""
        assert get_color_emoji("otro") == "⚫"

    def test_tipo_desconocido_retorna_negro(self):
        """Tipo no reconocido → emoji negro (default)."""
        assert get_color_emoji("desconocido") == "⚫"
