"""Fases B–D: episodio léxico, índice invertido, enseñanza → recuperación."""
import os
import tempfile

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.lexical_learning import ensenar_expresion, resolver_formas_aprendidas, revertir_episodio
from core.memory_service import aprender, buscar, ensenar_lexico
from core.paths import resolve_db_path


@pytest.fixture
def cerebro_tmp(tmp_path):
    db = str(tmp_path / "lex.db")
    c = SQLiteMemoryBioRAG(db)
    aprender(c, "scoring_pesos_bm25", "Pesos BM25 y ranking hibrido local.", consolidar=True)
    yield c
    c.cerrar_sistema()


def test_paths_respects_env(monkeypatch, tmp_path):
    p = str(tmp_path / "x.db")
    monkeypatch.setenv("BIORAG_PATH", p)
    assert resolve_db_path() == p


def test_ensenar_crea_episodio_e_indice(cerebro_tmp):
    out = ensenar_expresion(
        cerebro_tmp,
        "coeficientes multiplicativos de relevancia",
        "scoring_pesos_bm25",
        provenance="test",
    )
    assert out["ok"] is True
    hits = resolver_formas_aprendidas(cerebro_tmp, "coeficientes multiplicativos de relevancia")
    assert any(h["canonical_concept"] == "scoring_pesos_bm25" for h in hits)


def test_forma_ensenada_top1(cerebro_tmp):
    ensenar_lexico(
        cerebro_tmp,
        "ajuste ponderado del ranking BM25",
        "scoring_pesos_bm25",
    )
    resultados, _ = buscar(cerebro_tmp, "ajuste ponderado del ranking BM25", limite=5)
    conceptos = [r[0] for r in resultados]
    assert "scoring_pesos_bm25" in conceptos
    assert conceptos[0] == "scoring_pesos_bm25"


def test_no_fusiona_nodos(cerebro_tmp):
    aprender(cerebro_tmp, "otro_nodo", "Nodo distinto no alias.", consolidar=True)
    ensenar_expresion(cerebro_tmp, "otro nodo", "scoring_pesos_bm25")
    n = cerebro_tmp.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    assert n == 2


def test_revertir_episodio(cerebro_tmp):
    out = ensenar_expresion(cerebro_tmp, "panel cerebral", "scoring_pesos_bm25")
    assert revertir_episodio(cerebro_tmp, out["episode_id"])
    hits = resolver_formas_aprendidas(cerebro_tmp, "panel cerebral")
    assert hits == []
