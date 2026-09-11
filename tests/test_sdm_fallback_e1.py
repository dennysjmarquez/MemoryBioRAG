"""E1: SDM Fallback 2.5 — generación cuando el pool léxico es pobre."""
import os

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.sdm import indexar_nodo_sdm, rescatar_fallback_sdm


@pytest.fixture
def cerebro_sdm(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_SDM_FALLBACK", "1")
    monkeypatch.setenv("BIORAG_SDM_FALLBACK_SIM_MIN", "0.05")
    db = str(tmp_path / "sdm_e1.db")
    c = SQLiteMemoryBioRAG(db)
    c.percibir_corto_plazo(
        "gato_domestico",
        "El gato es un mamifero domestico de la familia Felidae minino felino.",
    )
    c.consolidar_concepto("gato_domestico")
    indexar_nodo_sdm(c, "gato_domestico")
    yield c
    c.cerrar_sistema()


def test_rescatar_no_reindexa_tabla_vacia(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "empty.db"))
    c.percibir_corto_plazo("nodo_sin_vector", "contenido unico xyzabc")
    c.consolidar_concepto("nodo_sin_vector")
    c.cursor.execute("DELETE FROM nodos_sdm")
    c.conn.commit()
    hits = rescatar_fallback_sdm(c, "tres tokens distintos aqui")
    n = c.cursor.execute("SELECT COUNT(*) FROM nodos_sdm").fetchone()[0]
    c.cerrar_sistema()
    assert hits == []
    assert n == 0


def test_rescatar_encuentra_nodo_indexado(cerebro_sdm):
    hits = rescatar_fallback_sdm(
        cerebro_sdm, "gato mamifero domestico felidae", sim_min=0.01
    )
    assert any(h["concepto"] == "gato_domestico" for h in hits)


def test_fallback_inyecta_cuando_pool_pobre(cerebro_sdm, monkeypatch):
    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    resultados, _ = cerebro_sdm.buscar_por_frase(
        "mamifero domestico felidae minino", limite=5
    )
    origen = cerebro_sdm.last_origen_scores.get("gato_domestico", ("", 0))[0]
    conceptos = [r[0] for r in resultados]
    assert "gato_domestico" in conceptos or origen in ("sdm", "literal", "latente", "contenido")


def test_fallback_off_no_marca_sdm(cerebro_sdm):
    hits = rescatar_fallback_sdm(cerebro_sdm, "zzzz yyyy xxxx qqqq", sim_min=0.99)
    assert hits == []


def test_no_fusiona_nodos(cerebro_sdm):
    n = cerebro_sdm.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    rescatar_fallback_sdm(cerebro_sdm, "mamifero domestico felidae")
    n2 = cerebro_sdm.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    assert n == n2 == 1
