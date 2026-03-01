"""Tests de prompts: build_parse_prompt y build_edit_prompt."""
from __future__ import annotations

from agents.groq_parser.prompts import (
    SYSTEM_PROMPT_EDIT,
    SYSTEM_PROMPT_PARSE,
    build_edit_prompt,
    build_parse_prompt,
)


class TestBuildParsePrompt:
    """Tests para build_parse_prompt."""

    def test_retorna_tupla_de_dos(self):
        """Debe retornar (system_prompt, user_prompt)."""
        result = build_parse_prompt("Hola", "2026-03-01", "10:00")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_contiene_fecha(self):
        """El system prompt debe incluir la fecha actual."""
        system, _ = build_parse_prompt("Hola", "2026-03-01", "10:00")
        assert "2026-03-01" in system

    def test_system_prompt_contiene_hora(self):
        """El system prompt debe incluir la hora actual."""
        system, _ = build_parse_prompt("Hola", "2026-03-01", "15:30")
        assert "15:30" in system

    def test_user_prompt_contiene_mensaje(self):
        """El user prompt debe incluir el mensaje original."""
        _, user = build_parse_prompt(
            "Agendame para mañana", "2026-03-01", "10:00"
        )
        assert "Agendame para mañana" in user

    def test_system_prompt_contiene_intenciones(self):
        """El system prompt enumera todas las intenciones posibles."""
        system, _ = build_parse_prompt("test", "2026-03-01", "10:00")
        assert "agendar" in system
        assert "cancelar" in system
        assert "editar" in system
        assert "listar_pendientes" in system
        assert "listar_historial" in system
        assert "listar_dia" in system
        assert "listar_cliente" in system
        assert "otro" in system

    def test_system_prompt_contiene_servicios(self):
        """El system prompt enumera todos los tipos de servicio."""
        system, _ = build_parse_prompt("test", "2026-03-01", "10:00")
        assert "instalacion" in system
        assert "revision" in system
        assert "mantenimiento" in system
        assert "presupuesto" in system
        assert "reparacion" in system

    def test_system_prompt_contiene_reglas(self):
        """El system prompt incluye las reglas de parseo."""
        system, _ = build_parse_prompt("test", "2026-03-01", "10:00")
        assert "No inventes datos" in system
        assert "null" in system

    def test_system_prompt_menciona_zona_horaria(self):
        """El system prompt menciona la zona horaria correcta."""
        system, _ = build_parse_prompt("test", "2026-03-01", "10:00")
        assert "America/Argentina/Buenos_Aires" in system


class TestBuildEditPrompt:
    """Tests para build_edit_prompt."""

    def test_retorna_tupla_de_dos(self):
        """Debe retornar (system_prompt, user_prompt)."""
        result = build_edit_prompt(
            evento_actual={"summary": "Test"},
            instruccion="Cambiá la hora",
            fecha_actual="2026-03-01",
            hora_actual="10:00",
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_contiene_evento_json(self):
        """El system prompt incluye el evento actual serializado."""
        evento = {"summary": "García - 260-111", "start": "2026-03-02"}
        system, _ = build_edit_prompt(
            evento_actual=evento,
            instruccion="Pasalo al viernes",
            fecha_actual="2026-03-01",
            hora_actual="10:00",
        )
        assert "García" in system
        assert "260-111" in system

    def test_system_prompt_contiene_instruccion(self):
        """El system prompt incluye la instrucción del usuario."""
        system, _ = build_edit_prompt(
            evento_actual={"summary": "Test"},
            instruccion="Pasalo al viernes a las 16",
            fecha_actual="2026-03-01",
            hora_actual="10:00",
        )
        assert "Pasalo al viernes a las 16" in system

    def test_user_prompt_contiene_instruccion(self):
        """El user prompt contiene la instrucción."""
        _, user = build_edit_prompt(
            evento_actual={"summary": "Test"},
            instruccion="Cambiá el servicio a instalación",
            fecha_actual="2026-03-01",
            hora_actual="10:00",
        )
        assert "Cambiá el servicio a instalación" in user

    def test_system_prompt_contiene_campos_posibles(self):
        """El system prompt enumera los campos de EditInstruction."""
        system, _ = build_edit_prompt(
            evento_actual={"summary": "Test"},
            instruccion="test",
            fecha_actual="2026-03-01",
            hora_actual="10:00",
        )
        assert "nueva_fecha" in system
        assert "nueva_hora" in system
        assert "nuevo_tipo_servicio" in system
        assert "nueva_direccion" in system
        assert "nuevo_telefono" in system
        assert "nueva_duracion_horas" in system

    def test_system_prompt_contiene_fecha_actual(self):
        """El system prompt contiene la fecha actual para resolver relativos."""
        system, _ = build_edit_prompt(
            evento_actual={"summary": "Test"},
            instruccion="test",
            fecha_actual="2026-03-05",
            hora_actual="14:00",
        )
        assert "2026-03-05" in system
        assert "14:00" in system


class TestConstantes:
    """Verificación de las constantes de prompts."""

    def test_system_prompt_parse_es_template(self):
        """SYSTEM_PROMPT_PARSE contiene placeholders."""
        assert "{fecha_actual}" in SYSTEM_PROMPT_PARSE
        assert "{hora_actual}" in SYSTEM_PROMPT_PARSE

    def test_system_prompt_edit_es_template(self):
        """SYSTEM_PROMPT_EDIT contiene placeholders."""
        assert "{evento_actual_json}" in SYSTEM_PROMPT_EDIT
        assert "{instruccion}" in SYSTEM_PROMPT_EDIT
        assert "{fecha_actual}" in SYSTEM_PROMPT_EDIT
        assert "{hora_actual}" in SYSTEM_PROMPT_EDIT
