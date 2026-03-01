"""Tests de los dataclasses Cliente y Servicio."""
from __future__ import annotations

from agents.db_manager.models import Cliente, Servicio


class TestCliente:
    def test_creacion_minima(self):
        c = Cliente(nombre_completo="García, Juan")
        assert c.nombre_completo == "García, Juan"
        assert c.ciudad == "San Rafael"
        assert c.id_cliente is None
        assert c.alias is None
        assert c.telefono is None

    def test_todos_los_campos(self):
        c = Cliente(
            id_cliente=1,
            nombre_completo="García, Juan",
            alias="Juancho",
            telefono="260-123456",
            direccion="Av. Rivadavia 100",
            ciudad="Mendoza",
            notas_equipamiento="DVR Hikvision 8ch",
        )
        assert c.id_cliente == 1
        assert c.alias == "Juancho"
        assert c.ciudad == "Mendoza"

    def test_str_retorna_nombre(self):
        c = Cliente(nombre_completo="López, Pedro")
        assert str(c) == "López, Pedro"

    def test_ciudad_default_san_rafael(self):
        c = Cliente(nombre_completo="Test")
        assert c.ciudad == "San Rafael"


class TestServicio:
    def test_creacion_minima(self):
        s = Servicio(id_cliente=1)
        assert s.id_cliente == 1
        assert s.estado == "pendiente"
        assert s.id_servicio is None

    def test_estado_personalizado(self):
        s = Servicio(id_cliente=1, estado="cancelado")
        assert s.estado == "cancelado"

    def test_todos_los_campos(self):
        s = Servicio(
            id_cliente=5,
            id_servicio=10,
            calendar_event_id="abc123",
            tipo_trabajo="instalacion",
            descripcion="Instalación de 8 cámaras",
            estado="realizado",
        )
        assert s.calendar_event_id == "abc123"
        assert s.tipo_trabajo == "instalacion"
        assert s.estado == "realizado"
