"""Tests de schemas: ParsedMessage, EditInstruction y validadores."""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from pydantic import ValidationError

from agents.groq_parser.schemas import (
    EditInstruction,
    Intencion,
    ParsedMessage,
    TipoServicio,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _future_date(days: int = 3) -> date:
    """Retorna una fecha futura segura para tests."""
    return date.today() + timedelta(days=days)


# ── ParsedMessage — Creación válida ──────────────────────────────────────────


class TestParsedMessageValido:
    """Tests de creación válida de ParsedMessage."""

    def test_creacion_minima_intencion_otro(self):
        """Solo intención 'otro' sin campos extra."""
        msg = ParsedMessage(intencion=Intencion.otro)
        assert msg.intencion == Intencion.otro
        assert msg.nombre_cliente is None
        assert msg.urgente is False

    def test_creacion_completa_agendar(self):
        """ParsedMessage con todos los campos de agendar."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="García",
            tipo_servicio=TipoServicio.instalacion,
            fecha=_future_date(),
            hora=time(10, 0),
            duracion_estimada_horas=3.0,
            direccion="Av. San Martín 456",
            telefono="2604567890",
        )
        assert msg.intencion == Intencion.agendar
        assert msg.nombre_cliente == "García"
        assert msg.duracion_estimada_horas == 3.0

    def test_creacion_listar_dia(self):
        """ParsedMessage para listar_dia con fecha_consulta."""
        msg = ParsedMessage(
            intencion=Intencion.listar_dia,
            fecha_consulta=_future_date(1),
        )
        assert msg.intencion == Intencion.listar_dia
        assert msg.fecha_consulta is not None

    def test_creacion_listar_cliente(self):
        """ParsedMessage para listar_cliente con cliente_consulta."""
        msg = ParsedMessage(
            intencion=Intencion.listar_cliente,
            cliente_consulta="Juan",
        )
        assert msg.cliente_consulta == "Juan"

    def test_urgente_true(self):
        """Campo urgente se setea correctamente."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            nombre_cliente="López",
            urgente=True,
        )
        assert msg.urgente is True


# ── ParsedMessage — 8 intenciones ────────────────────────────────────────────


class TestTodasLasIntenciones:
    """Verifica que las 8 intenciones se crean correctamente."""

    @pytest.mark.parametrize("intencion", list(Intencion))
    def test_cada_intencion_valida(self, intencion: Intencion):
        """Cada valor del enum Intencion debe crear un ParsedMessage válido."""
        msg = ParsedMessage(intencion=intencion)
        assert msg.intencion == intencion

    def test_total_intenciones_son_8(self):
        """El enum Intencion tiene exactamente 8 valores."""
        assert len(Intencion) == 8


# ── ParsedMessage — Validación de fecha ──────────────────────────────────────


class TestValidacionFecha:
    """Tests de validación de fecha no-pasada."""

    def test_fecha_pasada_lanza_validation_error(self):
        """Fecha anterior a hoy debe fallar."""
        with pytest.raises(ValidationError, match="anterior a hoy"):
            ParsedMessage(
                intencion=Intencion.agendar,
                fecha=date(2020, 1, 1),
            )

    def test_fecha_hoy_es_valida(self):
        """Fecha igual a hoy es válida."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            fecha=date.today(),
        )
        assert msg.fecha == date.today()

    def test_fecha_futura_es_valida(self):
        """Fecha futura es válida."""
        future = _future_date(30)
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            fecha=future,
        )
        assert msg.fecha == future

    def test_fecha_none_es_valida(self):
        """Fecha None no dispara validación."""
        msg = ParsedMessage(intencion=Intencion.agendar)
        assert msg.fecha is None


# ── ParsedMessage — Validación de teléfono ───────────────────────────────────


class TestValidacionTelefono:
    """Tests de validación de teléfono."""

    def test_telefono_valido_10_digitos(self):
        """10 dígitos es válido."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            telefono="2604567890",
        )
        assert msg.telefono == "2604567890"

    def test_telefono_con_guiones_se_limpia(self):
        """Guiones se eliminan, quedan solo dígitos."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            telefono="260-456-7890",
        )
        assert msg.telefono == "2604567890"

    def test_telefono_muy_corto_lanza_error(self):
        """Menos de 8 dígitos debe fallar."""
        with pytest.raises(ValidationError, match="entre 8 y 13"):
            ParsedMessage(
                intencion=Intencion.agendar,
                telefono="123",
            )

    def test_telefono_muy_largo_lanza_error(self):
        """Más de 13 dígitos debe fallar."""
        with pytest.raises(ValidationError, match="entre 8 y 13"):
            ParsedMessage(
                intencion=Intencion.agendar,
                telefono="12345678901234",
            )

    def test_telefono_none_es_valido(self):
        """Teléfono None no dispara validación."""
        msg = ParsedMessage(intencion=Intencion.agendar)
        assert msg.telefono is None


# ── ParsedMessage — Inferencia de duración ───────────────────────────────────


class TestInferenciaDuracion:
    """Tests de inferencia automática de duración."""

    def test_infiere_duracion_instalacion(self):
        """tipo=instalacion sin duración explícita → 3.0."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            tipo_servicio=TipoServicio.instalacion,
        )
        assert msg.duracion_estimada_horas == 3.0

    def test_infiere_duracion_revision(self):
        """tipo=revision sin duración explícita → 1.0."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            tipo_servicio=TipoServicio.revision,
        )
        assert msg.duracion_estimada_horas == 1.0

    def test_infiere_duracion_mantenimiento(self):
        """tipo=mantenimiento sin duración explícita → 2.0."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            tipo_servicio=TipoServicio.mantenimiento,
        )
        assert msg.duracion_estimada_horas == 2.0

    def test_infiere_duracion_reparacion(self):
        """tipo=reparacion sin duración explícita → 2.0."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            tipo_servicio=TipoServicio.reparacion,
        )
        assert msg.duracion_estimada_horas == 2.0

    def test_duracion_explicita_no_se_sobreescribe(self):
        """Si el usuario da duración, se respeta (no se infiere)."""
        msg = ParsedMessage(
            intencion=Intencion.agendar,
            tipo_servicio=TipoServicio.instalacion,
            duracion_estimada_horas=5.0,
        )
        assert msg.duracion_estimada_horas == 5.0

    def test_sin_tipo_no_infiere(self):
        """Sin tipo_servicio, duración queda None."""
        msg = ParsedMessage(intencion=Intencion.agendar)
        assert msg.duracion_estimada_horas is None


# ── EditInstruction ──────────────────────────────────────────────────────────


class TestEditInstruction:
    """Tests de EditInstruction."""

    def test_sin_campos_lanza_validation_error(self):
        """EditInstruction con todos None debe fallar."""
        with pytest.raises(ValidationError, match="al menos un campo"):
            EditInstruction()

    def test_valida_con_nueva_fecha(self):
        """Solo nueva_fecha es suficiente."""
        edit = EditInstruction(nueva_fecha=_future_date())
        assert edit.nueva_fecha is not None

    def test_valida_con_nueva_hora(self):
        """Solo nueva_hora es suficiente."""
        edit = EditInstruction(nueva_hora=time(16, 0))
        assert edit.nueva_hora == time(16, 0)

    def test_valida_con_nuevo_tipo_servicio(self):
        """Solo nuevo_tipo_servicio es suficiente."""
        edit = EditInstruction(nuevo_tipo_servicio=TipoServicio.instalacion)
        assert edit.nuevo_tipo_servicio == TipoServicio.instalacion

    def test_valida_con_nueva_direccion(self):
        """Solo nueva_direccion es suficiente."""
        edit = EditInstruction(nueva_direccion="Calle nueva 123")
        assert edit.nueva_direccion == "Calle nueva 123"

    def test_valida_con_nuevo_telefono(self):
        """Solo nuevo_telefono es suficiente."""
        edit = EditInstruction(nuevo_telefono="2604567890")
        assert edit.nuevo_telefono == "2604567890"

    def test_valida_con_nueva_duracion(self):
        """Solo nueva_duracion_horas es suficiente."""
        edit = EditInstruction(nueva_duracion_horas=2.5)
        assert edit.nueva_duracion_horas == 2.5

    def test_multiples_campos(self):
        """Múltiples campos a la vez también es válido."""
        edit = EditInstruction(
            nueva_fecha=_future_date(),
            nueva_hora=time(16, 0),
            nuevo_tipo_servicio=TipoServicio.reparacion,
        )
        assert edit.nueva_fecha is not None
        assert edit.nueva_hora == time(16, 0)
        assert edit.nuevo_tipo_servicio == TipoServicio.reparacion


# ── TipoServicio Enum ────────────────────────────────────────────────────────


class TestTipoServicio:
    """Tests del enum TipoServicio."""

    def test_total_tipos_son_6(self):
        """El enum TipoServicio tiene exactamente 6 valores."""
        assert len(TipoServicio) == 6

    @pytest.mark.parametrize("tipo", list(TipoServicio))
    def test_cada_tipo_es_string(self, tipo: TipoServicio):
        """Cada valor es un string."""
        assert isinstance(tipo.value, str)
