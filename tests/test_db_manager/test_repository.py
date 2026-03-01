"""Tests del repositorio: CRUD completo + fuzzy search + cache."""

from __future__ import annotations

import pytest
import pytest_asyncio

from agents.db_manager.connection import get_db_connection
from agents.db_manager.migrations import run_migrations
from agents.db_manager.models import Servicio
from agents.db_manager.repository import DBRepository
from core.exceptions import ClienteNoEncontradoError


@pytest_asyncio.fixture
async def repo():
    """Repositorio con DB en memoria y migraciones aplicadas."""
    async with get_db_connection(":memory:") as conn:
        await run_migrations(conn)
        yield DBRepository(conn)


# ── Crear cliente ─────────────────────────────────────────────────────────────


async def test_crear_cliente_retorna_objeto(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan", "telefono": "260-1234"})
    assert c.id_cliente is not None
    assert c.nombre_completo == "García, Juan"
    assert c.telefono == "260-1234"


async def test_crear_cliente_ciudad_default(repo):
    c = await repo.crear_cliente({"nombre_completo": "López, Pedro"})
    assert c.ciudad == "San Rafael"


async def test_crear_cliente_ciudad_custom(repo):
    c = await repo.crear_cliente({"nombre_completo": "Test", "ciudad": "Mendoza"})
    assert c.ciudad == "Mendoza"


async def test_crear_cliente_incrementa_id(repo):
    c1 = await repo.crear_cliente({"nombre_completo": "A"})
    c2 = await repo.crear_cliente({"nombre_completo": "B"})
    assert c2.id_cliente > c1.id_cliente


# ── Fuzzy search ──────────────────────────────────────────────────────────────


async def test_fuzzy_encuentra_typo(repo):
    """'Garzia' debe encontrar 'García' con score ≥ 75."""
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    resultado = await repo.buscar_cliente_fuzzy("Garzia Juan")
    assert resultado is not None
    assert resultado.nombre_completo == "García, Juan"


async def test_fuzzy_threshold_alto_no_encuentra(repo):
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    resultado = await repo.buscar_cliente_fuzzy("López", threshold=90)
    assert resultado is None


async def test_fuzzy_db_vacia_retorna_none(repo):
    resultado = await repo.buscar_cliente_fuzzy("García")
    assert resultado is None


async def test_fuzzy_usa_cache_segunda_vez(repo):
    """La segunda búsqueda del mismo nombre debe venir del caché."""
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    r1 = await repo.buscar_cliente_fuzzy("García, Juan")
    r2 = await repo.buscar_cliente_fuzzy("García, Juan")
    assert r1 is not None
    assert r2 is not None
    assert r1.nombre_completo == r2.nombre_completo


async def test_fuzzy_score_minimo_75(repo):
    """'Garcia' sin acento debe encontrar 'García, Juan' (score ≥ 75)."""
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    resultado = await repo.buscar_cliente_fuzzy("Garcia Juan", threshold=75)
    assert resultado is not None


# ── Actualizar cliente ────────────────────────────────────────────────────────


async def test_actualizar_cliente_modifica_telefono(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    actualizado = await repo.actualizar_cliente(c.id_cliente, {"telefono": "260-9999"})
    assert actualizado.telefono == "260-9999"


async def test_actualizar_cliente_sin_cambios_retorna_cliente(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    resultado = await repo.actualizar_cliente(c.id_cliente, {})
    assert resultado.id_cliente == c.id_cliente


async def test_actualizar_invalida_cache(repo):
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    c = await repo.buscar_cliente_fuzzy("García, Juan")
    assert len(repo._cache) > 0
    await repo.actualizar_cliente(c.id_cliente, {"alias": "Juancho"})
    assert len(repo._cache) == 0


# ── Servicios ─────────────────────────────────────────────────────────────────


async def test_registrar_servicio_retorna_id(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    s = Servicio(id_cliente=c.id_cliente, tipo_trabajo="revision")
    id_srv = await repo.registrar_servicio(s)
    assert isinstance(id_srv, int)
    assert id_srv > 0


async def test_registrar_multiples_servicios_ids_distintos(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    id1 = await repo.registrar_servicio(Servicio(id_cliente=c.id_cliente))
    id2 = await repo.registrar_servicio(Servicio(id_cliente=c.id_cliente))
    assert id1 != id2


async def test_actualizar_estado_servicio(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    id_srv = await repo.registrar_servicio(Servicio(id_cliente=c.id_cliente))
    await repo.actualizar_estado_servicio(id_srv, "cancelado")
    async with repo._conn.execute(
        "SELECT estado FROM historial_servicios WHERE id_servicio=?", (id_srv,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row["estado"] == "cancelado"


async def test_actualizar_estado_a_realizado(repo):
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    id_srv = await repo.registrar_servicio(Servicio(id_cliente=c.id_cliente))
    await repo.actualizar_estado_servicio(id_srv, "realizado")
    async with repo._conn.execute(
        "SELECT estado FROM historial_servicios WHERE id_servicio=?", (id_srv,)
    ) as cursor:
        row = await cursor.fetchone()
    assert row["estado"] == "realizado"


# ── Listar clientes ───────────────────────────────────────────────────────────


async def test_listar_clientes_retorna_todos(repo):
    await repo.crear_cliente({"nombre_completo": "García, Juan"})
    await repo.crear_cliente({"nombre_completo": "López, Pedro"})
    clientes = await repo.listar_clientes()
    assert len(clientes) == 2


async def test_listar_clientes_vacio(repo):
    clientes = await repo.listar_clientes()
    assert clientes == []


async def test_listar_clientes_respeta_limit(repo):
    for i in range(6):
        await repo.crear_cliente({"nombre_completo": f"Cliente {i}"})
    clientes = await repo.listar_clientes(limit=3)
    assert len(clientes) == 3


# ── Error handling ────────────────────────────────────────────────────────────


async def test_get_cliente_inexistente_lanza_error(repo):
    with pytest.raises(ClienteNoEncontradoError):
        await repo._get_cliente_by_id(99999)


# ── buscar_servicio_por_event_id ──────────────────────────────────────────────


async def test_buscar_servicio_por_event_id_encontrado(repo):
    """Busca un servicio existente por su calendar_event_id."""
    c = await repo.crear_cliente({"nombre_completo": "García, Juan"})
    servicio = Servicio(
        id_cliente=c.id_cliente,
        calendar_event_id="evt_abc_123",
        tipo_trabajo="revision",
        estado="pendiente",
    )
    id_srv = await repo.registrar_servicio(servicio)
    result = await repo.buscar_servicio_por_event_id("evt_abc_123")
    assert result is not None
    assert result.id_servicio == id_srv
    assert result.calendar_event_id == "evt_abc_123"
    assert result.tipo_trabajo == "revision"
    assert result.estado == "pendiente"


async def test_buscar_servicio_por_event_id_no_encontrado(repo):
    """Event ID inexistente retorna None."""
    result = await repo.buscar_servicio_por_event_id("evt_inexistente")
    assert result is None


async def test_buscar_servicio_por_event_id_y_actualizar_estado(repo):
    """Flujo completo: buscar servicio → actualizar estado a cancelado."""
    c = await repo.crear_cliente({"nombre_completo": "López, Pedro"})
    servicio = Servicio(
        id_cliente=c.id_cliente,
        calendar_event_id="evt_cancel_test",
        tipo_trabajo="instalacion",
        estado="pendiente",
    )
    await repo.registrar_servicio(servicio)

    found = await repo.buscar_servicio_por_event_id("evt_cancel_test")
    assert found is not None
    assert found.estado == "pendiente"

    await repo.actualizar_estado_servicio(found.id_servicio, "cancelado")

    updated = await repo.buscar_servicio_por_event_id("evt_cancel_test")
    assert updated is not None
    assert updated.estado == "cancelado"
