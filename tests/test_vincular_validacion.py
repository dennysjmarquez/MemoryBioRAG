import json
import pytest
from core.memory_store import SQLiteMemoryBioRAG
from core.mcp_server.synapses import register
from mcp.server.fastmcp import FastMCP


@pytest.fixture
def mcp_app(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_vincular.db")
    monkeypatch.setenv("BIORAG_PATH", db_file)

    cerebro = SQLiteMemoryBioRAG(db_path=db_file)
    cerebro.cerrar_sistema()

    mcp = FastMCP("test_biorag")
    register(mcp)
    return mcp, db_file


def test_vincular_rechaza_nodos_inexistentes(mcp_app):
    mcp, db_file = mcp_app
    tool_fn = None
    for tool in mcp._tool_manager.list_tools():
        if tool.name == "vincular":
            tool_fn = tool.fn
            break
    assert tool_fn is not None

    # Caso 1: Ambos nodos inexistentes
    res_raw = tool_fn(a="nodo_inexistente_1", b="nodo_inexistente_2")
    res = json.loads(res_raw)
    assert res["status"] == "error"
    assert "nodo_inexistente_1" in res["mensaje"]
    assert "nodo_inexistente_2" in res["mensaje"]

    # Caso 2: Solo uno existe
    cerebro = SQLiteMemoryBioRAG(db_path=db_file)
    cerebro.percibir_corto_plazo(
        "nodo_real_1",
        "contenido de prueba",
        sustantivos_clave="prueba,test",
    )
    cerebro.cerrar_sistema()

    res_raw2 = tool_fn(a="nodo_real_1", b="nodo_inexistente_2")
    res2 = json.loads(res_raw2)
    assert res2["status"] == "error"
    assert "nodo_inexistente_2" in res2["mensaje"]
    assert "nodo_real_1" not in res2["mensaje"]

    # Caso 3: Ambos existen -> Éxito
    cerebro = SQLiteMemoryBioRAG(db_path=db_file)
    cerebro.percibir_corto_plazo(
        "nodo_real_2",
        "segundo contenido",
        sustantivos_clave="prueba,test",
    )
    cerebro.cerrar_sistema()

    res_raw3 = tool_fn(a="nodo_real_1", b="nodo_real_2")
    res3 = json.loads(res_raw3)
    assert res3["status"] == "ok"
    assert "Sinapsis" in res3["mensaje"]
