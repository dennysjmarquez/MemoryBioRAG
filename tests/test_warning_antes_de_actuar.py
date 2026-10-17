"""
Tests para verificar la presencia de WARNING_ANTES_DE_ACTUAR al inicio de los resultados de búsqueda.
"""

import json
import sqlite3
import pytest
from core.mcp_server.search import WARNING_ANTES_DE_ACTUAR


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + tools MCP. Resetea singleton al inicio y fin."""
    db_path = str(tmp_path / "warning_test.db")
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


def test_warning_antes_de_actuar_en_recordar_textual(ctx):
    tools, db_path = ctx
    _insert_lp(db_path, "nodo_demo", contenido="arquitectura de software y diseno", sk="arquitectura,software")

    raw = tools["recordar"](query="arquitectura", sustantivos_clave="arquitectura,software")
    assert raw.startswith(WARNING_ANTES_DE_ACTUAR)


def test_warning_antes_de_actuar_en_buscar(ctx):
    tools, db_path = ctx
    _insert_lp(db_path, "nodo_demo_buscar", contenido="investigacion de reglas", sk="investigacion,reglas")

    raw = tools["buscar"](query="investigacion", sustantivos_clave="investigacion,reglas")
    assert raw.startswith(WARNING_ANTES_DE_ACTUAR)


def test_warning_antes_de_actuar_en_cronologico(ctx):
    tools, db_path = ctx
    _insert_lp(db_path, "nodo_reciente", contenido="evento temporal", sk="")

    raw = tools["recordar"](dias=1)
    assert raw.startswith(WARNING_ANTES_DE_ACTUAR)


def test_warning_antes_de_actuar_en_cero_resultados(ctx):
    tools, db_path = ctx
    raw = tools["recordar"](query="inexistente_xyz_123", sustantivos_clave="termino,inexistente")
    assert raw.startswith(WARNING_ANTES_DE_ACTUAR)
