"""
Tests T1 — Pre-flight Search: Parámetro `busqueda_previa` en `aprender` (Spec 004).

Hecho cuando:
  ✓ aprender(..., busqueda_previa=False) retorna error BUSQUEDA_PREVIA_REQUERIDA
  ✓ aprender(..., busqueda_previa=None) retorna error BUSQUEDA_PREVIA_REQUERIDA
  ✓ La validación de busqueda_previa se ejecuta ANTES que la de bridges y sustantivos_clave
  ✓ aprender(..., busqueda_previa=True) con parámetros válidos guarda correctamente
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
    db_path = str(tmp_path / "t1_preflight.db")
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
    "concepto": "nodo_test_preflight",
    "contenido": "Contenido para prueba de preflight search con suficiente extensión",
    "dimensiones": '{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
    "syn": "preflight,busqueda,previa,test,nodo",
    "bridges": VALID_BRIDGES,
    "sustantivos_clave": "prueba,preflight",
}


class TestT1PreflightBusquedaPrevia:
    """T1: Parámetro `busqueda_previa` en `aprender` y validación primera."""

    def test_aprender_sin_busqueda_previa_falla(self, ctx):
        tools, _ = ctx
        raw = tools["aprender"](**BASE_ARGS)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"
        assert "BÚSQUEDA PREVIA REQUERIDA" in res["mensaje"]

    def test_aprender_con_busqueda_previa_false_falla(self, ctx):
        tools, _ = ctx
        args = dict(BASE_ARGS)
        args["busqueda_previa"] = False
        raw = tools["aprender"](**args)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"

    def test_preflight_valida_antes_que_bridges_y_sustantivos(self, ctx):
        """Si falta bridges o sustantivos_clave, pero busqueda_previa no es True,
        el error prioritario debe ser BUSQUEDA_PREVIA_REQUERIDA."""
        tools, _ = ctx
        raw = tools["aprender"](
            concepto="nodo_incompleto",
            contenido="Contenido sin bridges ni sustantivos",
            dimensiones='{"emocion":["satisfaccion"]}',
            bridges=None,
            sustantivos_clave=None,
            busqueda_previa=False,
        )
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"

    def test_aprender_con_busqueda_previa_true_guarda_exitosamente(self, ctx):
        tools, db_path = ctx
        args = dict(BASE_ARGS)
        args["concepto"] = "nodo_exitoso"
        args["busqueda_previa"] = True
        raw = tools["aprender"](**args)
        res = _raw_json(raw)
        assert res["status"] == "ok"
        assert res["concepto"] == "nodo_exitoso"

        # Verificar en corto plazo
        conn = sqlite3.connect(db_path)
        fila = conn.execute("SELECT concepto, contenido FROM corto_plazo WHERE concepto = 'nodo_exitoso'").fetchone()
        conn.close()
        assert fila is not None
        assert fila[0] == "nodo_exitoso"
