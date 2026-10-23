"""Auto-expansión del MCP `recordar` (auto-paráfrasis PMI y auto-dimensiones).

Medido en docs/Mi neurona en el sistema/experimento_07_la_neurona_escucha: por el
camino real del agente ambas DAÑAN el recall (QA: R@5 no-literal 85.05 -> 95.10 sin
auto-paráfrasis; corpus no visto python-docs-es: R@1 31.48 -> 45.68). Quedan apagadas
por defecto; se reactivan con BIORAG_MCP_AUTO_PARAFRASIS=1 / BIORAG_MCP_AUTO_DIMS=1 y,
si se reactivan, son deterministas (antes: `list(set)[:10]` dependía de PYTHONHASHSEED).
"""
import os
import shutil

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SNAPSHOT = os.path.join(_RAIZ, "snapshots", "qa_escape_qcr_20260811.db")
Q = "arquitectura frontend memoria agente"


@pytest.fixture()
def recordar(tmp_path, monkeypatch):
    if not os.path.exists(_SNAPSHOT):
        pytest.skip("sin snapshot")
    db = str(tmp_path / "s.db")
    shutil.copyfile(_SNAPSHOT, db)
    monkeypatch.setenv("BIORAG_PATH", db)
    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    from core.memory_service import reset_cerebro
    from core.memory_store import SQLiteMemoryBioRAG
    reset_cerebro()
    vistos = []
    real = SQLiteMemoryBioRAG.buscar_por_frase

    def espia(self, frase, *a, **kw):
        vistos.append(kw)
        return real(self, frase, *a, **kw)
    monkeypatch.setattr(SQLiteMemoryBioRAG, "buscar_por_frase", espia)
    import mcp_server as m
    tools = {t.name: t.fn for t in m._build_server()._tool_manager.list_tools()}

    def llamar(**kw):
        vistos.clear()
        tools["recordar"](query=Q, sustantivos_clave="arquitectura,memoria", **kw)
        return vistos[0]
    yield llamar
    reset_cerebro()


def test_por_defecto_no_inventa_parafrasis_ni_dimensiones(recordar, monkeypatch):
    monkeypatch.delenv("BIORAG_MCP_AUTO_PARAFRASIS", raising=False)
    monkeypatch.delenv("BIORAG_MCP_AUTO_DIMS", raising=False)
    kw = recordar()
    assert not kw.get("parafrasis_list") and not kw.get("dimensiones_ids")
    # lo que manda el agente se respeta tal cual
    kw = recordar(parafrasis="diseño de la memoria,componentes visuales")
    assert kw["parafrasis_list"] == ["diseño de la memoria", "componentes visuales"]


def test_reactivadas_son_deterministas_y_eligen_lo_mas_fuerte(recordar, monkeypatch):
    monkeypatch.setenv("BIORAG_MCP_AUTO_PARAFRASIS", "1")
    monkeypatch.setenv("BIORAG_MCP_AUTO_DIMS", "1")
    a, b = recordar(), recordar()
    assert a["parafrasis_list"] and a["parafrasis_list"] == b["parafrasis_list"]
    assert a["dimensiones_ids"] and a["dimensiones_ids"] == b["dimensiones_ids"]
    # las paráfrasis van de la más fuerte a la más débil (NPMI), no en orden de hash
    from core.memory_service import get_cerebro
    from core.pmi_semantico import pares_fuertes, _tokenizar
    from core.stemmer_es import stem
    q = _tokenizar(Q)
    fuerza = {}
    for t in q:
        if len(t) >= 3:
            for tok, npmi in pares_fuertes(get_cerebro().cursor, stem(t), top_n=5):
                if npmi >= .35 and tok not in q:
                    fuerza[tok] = max(npmi, fuerza.get(tok, 0.0))
    esperado = [t for t, _ in sorted(fuerza.items(), key=lambda x: (-x[1], x[0]))[:10]]
    assert a["parafrasis_list"] == esperado
