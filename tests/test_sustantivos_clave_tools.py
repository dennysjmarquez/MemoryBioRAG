"""
Tests T4 — Tools MCP `biorag_agregar_sustantivos` y `biorag_sustantivos` (Spec 001).

RFs cubiertos: RF-16, RF-17.

Hecho cuando:
  ✓ biorag_agregar_sustantivos(concepto="nodo_test", sustantivos_clave="a,b") → {"status":"ok","sustantivos_anteriores":"","sustantivos_nuevos":"a,b"}
  ✓ biorag_agregar_sustantivos(concepto="nodo_inexistente", ...) → error NODO_NO_ENCONTRADO
  ✓ biorag_agregar_sustantivos con nodo que ya tiene campo → muestra sustantivos_anteriores vs sustantivos_nuevos
  ✓ biorag_agregar_sustantivos con nodo en corto_plazo → actualiza en corto_plazo
  ✓ biorag_agregar_sustantivos con formato/cantidad inválida → retorna error de validación
  ✓ biorag_sustantivos(concepto="nodo_test") → {"status":"ok","sustantivos_clave":"a,b","items":["a","b"]}
  ✓ biorag_sustantivos(concepto="nodo_inexistente") → error NODO_NO_ENCONTRADO
  ✓ biorag_sustantivos con nodo sin campo → {"status":"ok","sustantivos_clave":"","items":[]}
"""

import json
import sqlite3
import pytest


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + tools MCP. Resetea singleton al inicio y fin."""
    db_path = str(tmp_path / "t4_test.db")
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


def _insert_lp(db_path, concepto, contenido="Contenido de prueba", sk=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, estado, peso_sinaptico, sustantivos_clave) "
        "VALUES (?, ?, 1, 'activo', 1.0, ?)",
        (concepto, contenido, sk),
    )
    conn.commit()
    conn.close()


def _insert_cp(db_path, concepto, contenido="Contenido corto plazo", sk=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO corto_plazo (concepto, contenido, categoria, sustantivos_clave) "
        "VALUES (?, ?, 1, ?)",
        (concepto, contenido, sk),
    )
    conn.commit()
    conn.close()


class TestT4AgregarSustantivos:
    """RF-16: Tool `agregar_sustantivos`."""

    def test_agregar_sustantivos_nodo_existente_vacio(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_test", sk="")
        raw = tools["agregar_sustantivos"](concepto="nodo_test", sustantivos_clave="servidor,backend")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["concepto"] == "nodo_test"
        assert res["sustantivos_anteriores"] == ""
        assert res["sustantivos_nuevos"] == "servidor,backend"

        # Verificar en DB
        conn = sqlite3.connect(db_path)
        val = conn.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_test'").fetchone()[0]
        conn.close()
        assert val == "servidor,backend"

    def test_agregar_sustantivos_nodo_inexistente(self, ctx):
        tools, _ = ctx
        raw = tools["agregar_sustantivos"](concepto="nodo_fantasma", sustantivos_clave="servidor,backend")
        res = json.loads(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "NODO_NO_ENCONTRADO"

    def test_agregar_sustantivos_sobrescribe_existente(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_con_sk", sk="viejo_uno,viejo_dos")
        raw = tools["agregar_sustantivos"](concepto="nodo_con_sk", sustantivos_clave="nuevo_uno,nuevo_dos,nuevo_tres")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["sustantivos_anteriores"] == "viejo_uno,viejo_dos"
        assert res["sustantivos_nuevos"] == "nuevo_uno,nuevo_dos,nuevo_tres"

    def test_agregar_sustantivos_fallback_corto_plazo(self, ctx):
        tools, db_path = ctx
        _insert_cp(db_path, "nodo_en_cp", sk="")
        raw = tools["agregar_sustantivos"](concepto="nodo_en_cp", sustantivos_clave="buffer_uno,buffer_dos")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["sustantivos_nuevos"] == "buffer_uno,buffer_dos"

        conn = sqlite3.connect(db_path)
        val = conn.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = 'nodo_en_cp'").fetchone()[0]
        conn.close()
        assert val == "buffer_uno,buffer_dos"

    def test_agregar_sustantivos_validaciones(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_validar", sk="")

        # Ausente
        r1 = json.loads(tools["agregar_sustantivos"](concepto="nodo_validar", sustantivos_clave=""))
        assert r1["status"] == "error"
        assert r1["codigo"] == "SUSTANTIVOS_CLAVE_AUSENTES"

        # Cantidad inválida (1 término)
        r2 = json.loads(tools["agregar_sustantivos"](concepto="nodo_validar", sustantivos_clave="solo_uno"))
        assert r2["status"] == "error"
        assert r2["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"

        # Cantidad inválida (5 términos)
        r3 = json.loads(tools["agregar_sustantivos"](concepto="nodo_validar", sustantivos_clave="a,b,c,d,e"))
        assert r3["status"] == "error"
        assert r3["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"

        # Formato inválido (@ no permitido)
        r4 = json.loads(tools["agregar_sustantivos"](concepto="nodo_validar", sustantivos_clave="server@error,backend"))
        assert r4["status"] == "error"
        assert r4["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"


class TestT4ConsultarSustantivos:
    """RF-17: Tool `sustantivos`."""

    def test_consultar_sustantivos_existente(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_con_datos", sk="servidor,backend,timeout")
        raw = tools["sustantivos"](concepto="nodo_con_datos")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["concepto"] == "nodo_con_datos"
        assert res["sustantivos_clave"] == "servidor,backend,timeout"
        assert res["items"] == ["servidor", "backend", "timeout"]

    def test_consultar_sustantivos_sin_campo(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_sin_datos", sk="")
        raw = tools["sustantivos"](concepto="nodo_sin_datos")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["concepto"] == "nodo_sin_datos"
        assert res["sustantivos_clave"] == ""
        assert res["items"] == []

    def test_consultar_sustantivos_inexistente(self, ctx):
        tools, _ = ctx
        raw = tools["sustantivos"](concepto="nodo_que_no_existe")
        res = json.loads(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "NODO_NO_ENCONTRADO"

    def test_consultar_sustantivos_en_corto_plazo(self, ctx):
        tools, db_path = ctx
        _insert_cp(db_path, "nodo_reciente_cp", sk="memoria,sesion")
        raw = tools["sustantivos"](concepto="nodo_reciente_cp")
        res = json.loads(raw)
        assert res["status"] == "ok"
        assert res["sustantivos_clave"] == "memoria,sesion"
        assert res["items"] == ["memoria", "sesion"]
