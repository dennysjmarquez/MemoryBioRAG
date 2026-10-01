"""
Tests T2 — Quitar restricción temporal en `actualizar` y añadir soporte `sobrescribir` (Spec 004).

Hecho cuando:
  ✓ actualizar(concepto='nodo_antiguo', ...) actualiza sin error de tiempo (sin 'fuera_de_ventana')
  ✓ actualizar(concepto='nodo_inexistente', ...) sigue retornando error descriptivo
  ✓ actualizar(concepto='nodo', contenido='nuevo', sobrescribir=True) sobrescribe totalmente
  ✓ pytest tests/test_actualizar_sin_restriccion_temporal.py -q → tests en verde
"""

import json
import time
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
    db_path = str(tmp_path / "t2_actualizar.db")
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


def _insert_lp(db_path, concepto, contenido="Contenido viejo", creado_en=None, sinonimos="viejo_syn", sk="viejo_uno,viejo_dos"):
    conn = sqlite3.connect(db_path)
    ts = creado_en if creado_en is not None else (time.time() - 86400 * 365)  # 1 año atrás
    conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, estado, peso_sinaptico, sinonimos, sustantivos_clave, creado_en) "
        "VALUES (?, ?, 1, 'activo', 1.0, ?, ?, ?)",
        (concepto, contenido, sinonimos, sk, ts),
    )
    conn.commit()
    conn.close()


class TestT2ActualizarSinRestriccionTemporal:
    """T2: Quitar ventana temporal y soportar modo sobrescribir en actualizar."""

    def test_actualizar_nodo_antiguo_un_ano_atras(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_antiguo", contenido="Contenido original de hace 1 año", creado_en=time.time() - 86400 * 365)

        raw = tools["actualizar"](
            concepto="nodo_antiguo",
            contenido="Contenido actualizado hoy sin restricción temporal",
        )
        res = _raw_json(raw)
        assert res["status"] == "ok", f"Fallo con respuesta: {res}"
        assert "fuera_de_ventana" not in res.get("status", "")

        # Verificar en DB
        conn = sqlite3.connect(db_path)
        fila = conn.execute("SELECT contenido FROM largo_plazo WHERE concepto = 'nodo_antiguo'").fetchone()
        conn.close()
        assert fila[0] == "Contenido actualizado hoy sin restricción temporal"

    def test_actualizar_nodo_inexistente_retorna_error(self, ctx):
        tools, _ = ctx
        raw = tools["actualizar"](
            concepto="nodo_no_existe",
            contenido="Nuevo contenido",
        )
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert "no encontrado" in res["mensaje"].lower()

    def test_actualizar_sin_campos_retorna_sin_cambios(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_sin_cambios", creado_en=time.time() - 100000)
        raw = tools["actualizar"](concepto="nodo_sin_cambios")
        res = _raw_json(raw)
        assert res["status"] == "sin_cambios"

    def test_actualizar_modo_sobrescribir(self, ctx):
        tools, db_path = ctx
        _insert_lp(
            db_path,
            "nodo_version",
            contenido="Versión 1.0 obsoleta con datos viejos",
            sinonimos="v1,antiguo,obsoleto",
            sk="version,vieja",
            creado_en=time.time() - 86400 * 30,
        )

        raw = tools["actualizar"](
            concepto="nodo_version",
            contenido="Versión 2.0 definitiva con arquitectura limpia",
            sinonimos="v2,nueva,arquitectura",
            sustantivos_clave="version,nueva,arquitectura",
            sobrescribir=True,
        )
        res = _raw_json(raw)
        assert res["status"] == "ok"
        assert res.get("sobrescrito") is True or "contenido" in res.get("campos_modificados", [])

        # Verificar en DB que todo quedó sobrescrito
        conn = sqlite3.connect(db_path)
        fila = conn.execute(
            "SELECT contenido, sinonimos, sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_version'"
        ).fetchone()
        conn.close()
        assert fila[0] == "Versión 2.0 definitiva con arquitectura limpia"
        assert fila[1] == "v2,nueva,arquitectura"
        assert fila[2] == "version,nueva,arquitectura"
