"""
Tests T3 — Parámetro `vincular_con` en `aprender` (Spec 004).

Hecho cuando:
  ✓ aprender(..., busqueda_previa=True, vincular_con=["nodo_a"]) crea el nodo y la sinapsis con nodo_a
  ✓ aprender(..., busqueda_previa=True, vincular_con=["nodo_a", "nodo_b"]) crea múltiples sinapsis
  ✓ aprender(..., busqueda_previa=True, vincular_con="nodo_a,nodo_b") soporta formato string
  ✓ Si un concepto en vincular_con no existe, el nodo se guarda correctamente sin error fatal
"""

import json
import sqlite3
import pytest


def _raw_json(raw):
    idx = raw.find("{")
    if idx != -1:
        return json.loads(raw[idx:])
    return json.loads(raw)


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + tools MCP. Resetea singleton al inicio y fin."""
    db_path = str(tmp_path / "t3_vincular.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)
    cerebro.cerrar_sistema()

    from core.memory_service import reset_cerebro
    reset_cerebro()

    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    yield tools, db_path
    reset_cerebro()


VALID_BRIDGES = [
    {"text": "modo reposo del sistema de memoria", "angle": "sinonimo"},
    {"text": "proceso que genera ideas en silencio", "angle": "problema"},
    {"text": "hilos de pensamiento espontaneo", "angle": "solucion"},
    {"text": "cerebro piensa solo cuando nadie pregunta", "angle": "situacion"},
    {"text": "que pasa cuando no hay actividad en BioRAG", "angle": "ingenuo"},
]

BASE_ARGS = {
    "contenido": "Contenido del nodo para verificar vinculacion en aprender",
    "dimensiones": '{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
    "syn": "vinculacion,sinapsis,aristas,test,nodo",
    "bridges": VALID_BRIDGES,
    "sustantivos_clave": "vinculacion,sinapsis",
    "busqueda_previa": True,
}


def _insert_lp(db_path, concepto):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, estado, peso_sinaptico) "
        "VALUES (?, 'Contenido preexistente', 1, 'activo', 1.0)",
        (concepto,),
    )
    conn.commit()
    conn.close()


class TestT3VincularConEnAprender:
    """T3: Parámetro `vincular_con` en `aprender`."""

    def test_aprender_con_vincular_con_lista_un_nodo(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_destino_a")

        raw = tools["aprender"](
            concepto="nodo_origen_1",
            vincular_con=["nodo_destino_a"],
            **BASE_ARGS
        )
        res = _raw_json(raw)
        assert res["status"] == "ok"

        # Verificar que la sinapsis existe en la base de datos
        conn = sqlite3.connect(db_path)
        sinapsis = conn.execute(
            "SELECT origen, destino FROM sinapsis WHERE origen = 'nodo_origen_1' AND destino = 'nodo_destino_a'"
        ).fetchone()
        sinapsis_rev = conn.execute(
            "SELECT origen, destino FROM sinapsis WHERE origen = 'nodo_destino_a' AND destino = 'nodo_origen_1'"
        ).fetchone()
        conn.close()

        assert sinapsis is not None, "Sinapsis origen->destino no fue creada"
        assert sinapsis_rev is not None, "Sinapsis bidireccional destino->origen no fue creada"

    def test_aprender_con_vincular_con_multiples_nodos(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_x")
        _insert_lp(db_path, "nodo_y")

        raw = tools["aprender"](
            concepto="nodo_multiple",
            vincular_con=["nodo_x", "nodo_y"],
            **BASE_ARGS
        )
        res = _raw_json(raw)
        assert res["status"] == "ok"

        conn = sqlite3.connect(db_path)
        filas = conn.execute(
            "SELECT destino FROM sinapsis WHERE origen = 'nodo_multiple'"
        ).fetchall()
        destinos = {f[0] for f in filas}
        conn.close()

        assert "nodo_x" in destinos
        assert "nodo_y" in destinos

    def test_aprender_con_vincular_con_formato_string(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_str_1")
        _insert_lp(db_path, "nodo_str_2")

        raw = tools["aprender"](
            concepto="nodo_origen_str",
            vincular_con="nodo_str_1, nodo_str_2",
            **BASE_ARGS
        )
        res = _raw_json(raw)
        assert res["status"] == "ok"

        conn = sqlite3.connect(db_path)
        filas = conn.execute(
            "SELECT destino FROM sinapsis WHERE origen = 'nodo_origen_str'"
        ).fetchall()
        destinos = {f[0] for f in filas}
        conn.close()

        assert "nodo_str_1" in destinos
        assert "nodo_str_2" in destinos

    def test_aprender_con_vincular_con_nodo_inexistente_no_aborta(self, ctx):
        tools, db_path = ctx
        raw = tools["aprender"](
            concepto="nodo_resiliente",
            vincular_con=["nodo_que_aun_no_existe"],
            **BASE_ARGS
        )
        res = _raw_json(raw)
        assert res["status"] == "ok"

        conn = sqlite3.connect(db_path)
        nodo_guardado = conn.execute(
            "SELECT concepto FROM corto_plazo WHERE concepto = 'nodo_resiliente'"
        ).fetchone()
        conn.close()
        assert nodo_guardado is not None
