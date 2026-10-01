"""
T4 — Tests: alias `guardar` hereda busqueda_previa y vincular_con.

Verifica que la tool MCP `guardar` tiene exactamente el mismo contrato
que `aprender` respecto al pre-flight check (Invariante Spec 004) y
la vinculación automática (T3 Spec 004).
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
    db_path = str(tmp_path / "t4_guardar_alias.db")
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
    {"text": "alias de la herramienta aprender en el sistema biorag", "angle": "sinonimo"},
    {"text": "permite guardar informacion sin conocer el nombre tecnico aprender", "angle": "problema"},
    {"text": "redirige internamente a aprender con los mismos parametros", "angle": "solucion"},
    {"text": "agente llama guardar en lugar de aprender por convencion", "angle": "situacion"},
    {"text": "que diferencia hay entre guardar y aprender en biorag", "angle": "ingenuo"},
]

BASE_ARGS = {
    "concepto": "nodo_test_guardar_alias",
    "contenido": "Contenido para probar el alias guardar con suficiente extension textual",
    "syn": "guardar_alias,test_guardar,alias_aprender,nodo_guardar",
    "dimensiones": '{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
    "bridges": VALID_BRIDGES,
    "sustantivos_clave": "alias,guardar,test",
}


class TestGuardarPreflightCheck:
    """guardar debe rechazar la llamada si busqueda_previa != True."""

    def test_guardar_sin_busqueda_previa_retorna_error(self, ctx):
        tools, _ = ctx
        raw = tools["guardar"](**BASE_ARGS)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"

    def test_guardar_con_busqueda_previa_false_retorna_error(self, ctx):
        tools, _ = ctx
        args = dict(BASE_ARGS, busqueda_previa=False)
        raw = tools["guardar"](**args)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"

    def test_preflight_gana_sobre_bridges_ausentes(self, ctx):
        """BUSQUEDA_PREVIA_REQUERIDA debe ocurrir aunque bridges falte."""
        tools, _ = ctx
        raw = tools["guardar"](
            concepto="nodo_guardar_sin_bridges",
            contenido="Contenido sin bridges.",
            bridges=None,
            busqueda_previa=False,
        )
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"

    def test_guardar_con_busqueda_previa_true_guarda_exitosamente(self, ctx):
        tools, db_path = ctx
        args = dict(BASE_ARGS, busqueda_previa=True)
        raw = tools["guardar"](**args)
        res = _raw_json(raw)
        assert res["status"] == "ok", f"Error inesperado: {res}"
        assert res["concepto"] == "nodo_test_guardar_alias"

        conn = sqlite3.connect(db_path)
        fila = conn.execute(
            "SELECT concepto FROM corto_plazo WHERE concepto = 'nodo_test_guardar_alias'"
        ).fetchone()
        conn.close()
        assert fila is not None


class TestGuardarVincularCon:
    """guardar con vincular_con establece sinapsis igual que aprender."""

    def _guardar_nodo(self, tools, concepto, contenido, sustantivos):
        """Helper para crear nodos auxiliares en tests."""
        return _raw_json(tools["guardar"](
            concepto=concepto,
            contenido=contenido,
            bridges=VALID_BRIDGES,
            syn="test_aux,nodo_auxiliar,guardar_test",
            dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
            sustantivos_clave=sustantivos,
            busqueda_previa=True,
        ))

    def test_vincular_con_lista_crea_sinapsis(self, ctx):
        tools, db_path = ctx
        # Crear nodo destino
        r = self._guardar_nodo(tools, "nodo_destino_g", "Nodo destino para sinapsis desde guardar.", "destino,sinapsis,test")
        assert r["status"] == "ok", f"Error creando destino: {r}"

        # Crear nodo origen vinculado
        raw = tools["guardar"](
            concepto="nodo_origen_g",
            contenido="Nodo origen que vincula bidireccionalmente desde guardar.",
            bridges=VALID_BRIDGES,
            syn="origen_g,source_guardar,sinapsis_guardar",
            dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
            sustantivos_clave="origen,sinapsis,guardar",
            busqueda_previa=True,
            vincular_con=["nodo_destino_g"],
        )
        res = _raw_json(raw)
        assert res["status"] == "ok", f"Error creando origen: {res}"
        assert res.get("sinapsis", 0) >= 1

        # Verificar la sinapsis en DB
        conn = sqlite3.connect(db_path)
        arista = conn.execute(
            "SELECT 1 FROM sinapsis WHERE origen='nodo_origen_g' AND destino='nodo_destino_g'"
        ).fetchone()
        conn.close()
        assert arista is not None

    def test_vincular_con_concepto_inexistente_no_aborta_guardar(self, ctx):
        tools, _ = ctx
        raw = tools["guardar"](
            concepto="nodo_guardar_vinculo_huerfano",
            contenido="Nodo que intenta vincular con un concepto que no existe.",
            bridges=VALID_BRIDGES,
            syn="guardar_huerfano,vinculo_huerfano,test_guardar",
            dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
            sustantivos_clave="huerfano,vinculo,guardar",
            busqueda_previa=True,
            vincular_con=["nodo_xyz_no_existe_guardar_12345"],
        )
        res = _raw_json(raw)
        assert res["status"] == "ok", f"Error inesperado: {res}"

    def test_vincular_con_string_funciona_en_guardar(self, ctx):
        """vincular_con acepta string simple ademas de lista."""
        tools, _ = ctx
        # Crear destino
        r = self._guardar_nodo(tools, "nodo_str_destino_g", "Destino para vincular via string desde guardar.", "destino,string,guardar")
        assert r["status"] == "ok", f"Error creando destino: {r}"

        raw = tools["guardar"](
            concepto="nodo_str_origen_g",
            contenido="Origen que vincula con string desde alias guardar.",
            bridges=VALID_BRIDGES,
            syn="str_origen_g,origen_string_guardar,alias_string",
            dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
            sustantivos_clave="origen,string,guardar",
            busqueda_previa=True,
            vincular_con="nodo_str_destino_g",
        )
        res = _raw_json(raw)
        assert res["status"] == "ok", f"Error inesperado: {res}"
