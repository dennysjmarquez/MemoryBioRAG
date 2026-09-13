import logging
"""
Tests de OPT-NUEVA-5: etiquetado epistemico sin abstencion + puente DMN.

Verifica que:
1. El ranking devuelto es IDENTICO con flag ON/OFF (R9 vs E13: nunca recorta).
2. Metadatos correctos: conocido / incertidumbre_parcial / vacio_cognitivo.
3. Pool vacio -> vacio_cognitivo + encolado en estado_hormiga (vacios_cognitivos).
4. Flag OFF -> no escribe claves F6 ni encola.
5. Query vacia -> sin_consulta, sin encolar.
6. Encolado con dedup + merge preserva claves ADN/E13 previas.
"""
import json
import os
import sys

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import core.memory_store as ms
from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture
def cerebro_tmp(tmp_path, monkeypatch):
    """DB aislada + hormiga aislada + flag ON explicito."""
    db_file = str(tmp_path / "test_epistemico.db")
    monkeypatch.setattr(ms, "EPISTEMICO_METADATA", True)
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", str(tmp_path / "hormiga_test.json"))
    return SQLiteMemoryBioRAG(db_path=db_file)


def _pool_fuerte():
    return [
        ("nodo_a", "contenido a", 0.9, "activo", 0.90, ""),
        ("nodo_b", "contenido b", 0.8, "activo", 0.80, ""),
        ("nodo_c", "contenido c", 0.7, "activo", 0.70, ""),
    ]


def test_ranking_intacto_on_vs_off(tmp_path, monkeypatch):
    """ON/OFF devuelven pools identicos end-to-end (cero interferencia)."""
    db_file = str(tmp_path / "test_epi_rank.db")
    cz = SQLiteMemoryBioRAG(db_path=db_file)
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('manzana_roja', 'una manzana roja y jugosa', 0.9, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('tornillo_acero', 'tornillo de acero inoxidable', 0.8, 'activo')"
    )
    cz.conn.commit()
    monkeypatch.setattr(ms, "EPISTEMICO_METADATA", True)
    pool_on, total_on = cz.buscar_por_frase("manzana roja", limite=5)
    monkeypatch.setattr(ms, "EPISTEMICO_METADATA", False)
    pool_off, total_off = cz.buscar_por_frase("manzana roja", limite=5)
    assert pool_on == pool_off and total_on == total_off


def test_pool_no_mutado_por_hook(cerebro_tmp):
    """El hook no muta la lista que recibe (mismo objeto, mismo orden)."""
    pool = _pool_fuerte()
    antes = [tuple(r) for r in pool]
    cerebro_tmp._epistemico_publicar("q", pool, len(pool))
    assert [tuple(r) for r in pool] == antes
    assert len(pool) == 3


def test_pool_fuerte_es_conocido(cerebro_tmp):
    """Scores altos + dims compartidas -> conocido, sin encolar."""
    cz = cerebro_tmp
    for c in ("nodo_a", "nodo_b", "nodo_c"):
        cz.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
            " VALUES (?, 'x', 0.5, 'activo')",
            (c,),
        )
        cz.cursor.execute(
            "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id)"
            " VALUES (?, 7)",
            (c,),
        )
    cz.conn.commit()
    cz._epistemico_publicar("q fuerte", _pool_fuerte(), 3)
    info = cz.last_estado_epistemico
    assert info["estado_epistemico"] == "conocido"
    assert info["Ce"] == pytest.approx(0.89, abs=0.01)
    assert info["epistemico_n_resultados"] == 3
    assert not os.path.exists(os.environ["BIORAG_DMN_ESTADO_PATH"])


def test_pool_vacio_es_vacio_y_encola(cerebro_tmp):
    """Pool vacio -> vacio_cognitivo + entrada en la cola DMN."""
    cz = cerebro_tmp
    path = os.environ["BIORAG_DMN_ESTADO_PATH"]
    cz._epistemico_publicar("termino inexistente xyz", [], 0)
    info = cz.last_estado_epistemico
    assert info["estado_epistemico"] == "vacio_cognitivo"
    assert info["Ce"] == 0.0
    hormiga = json.load(open(path, encoding="utf-8"))
    terms = [e["termino"] for e in hormiga.get("vacios_cognitivos", [])]
    assert "termino inexistente xyz" in terms


def test_flag_off_no_escribe_ni_encola(tmp_path, monkeypatch):
    """Flag OFF: sin claves F6 ni archivo hormiga."""
    db_file = str(tmp_path / "test_epi_off.db")
    hpath = str(tmp_path / "hormiga_off.json")
    monkeypatch.setattr(ms, "EPISTEMICO_METADATA", False)
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", hpath)
    cz = SQLiteMemoryBioRAG(db_path=db_file)
    cz.buscar_por_frase("algo", limite=5)
    assert "estado_epistemico" not in cz.last_estado_epistemico
    assert not os.path.exists(hpath)


def test_query_vacia_es_sin_consulta(cerebro_tmp):
    """Query vacia: sin_consulta, sin encolar (no hubo busqueda)."""
    cz = cerebro_tmp
    pool, total = cz.buscar_por_frase("   ", limite=5)
    assert (pool, total) == ([], 0)
    assert cz.last_estado_epistemico["estado_epistemico"] == "sin_consulta"
    assert not os.path.exists(os.environ["BIORAG_DMN_ESTADO_PATH"])


def test_encolado_dedup_y_merge_preserva_adn(cerebro_tmp):
    """Dedup exacto + merge no pisa claves ADN/E13 previas."""
    cz = cerebro_tmp
    path = os.environ["BIORAG_DMN_ESTADO_PATH"]
    cz.last_estado_epistemico = {
        "estado": "x_adn",
        "confianza_epistemica": 0.5,
    }
    cz._epistemico_publicar("mismo vacio", [], 0)
    cz._epistemico_publicar("mismo vacio", [], 0)
    hormiga = json.load(open(path, encoding="utf-8"))
    terms = [e["termino"] for e in hormiga.get("vacios_cognitivos", [])]
    assert terms.count("mismo vacio") == 1
    assert cz.last_estado_epistemico["estado"] == "x_adn"
    assert cz.last_estado_epistemico["confianza_epistemica"] == 0.5
    assert cz.last_estado_epistemico["estado_epistemico"] == "vacio_cognitivo"
def test_fallo_epistemico_deja_rastro_y_no_rompe_busqueda(cerebro_tmp, monkeypatch, caplog):
    """Protocolo #12: el fallo epistémico loguea WARNING y la búsqueda intacta."""
    import core.memory_store as ms
    cz = cerebro_tmp
    assert ms.EPISTEMICO_METADATA == 1
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('manzana_roja', 'una manzana roja y jugosa', 0.9, 'activo')"
    )
    cz.conn.commit()

    def _boom(self, pagina):
        raise RuntimeError("tabla dimensiones ausente (simulado)")
    monkeypatch.setattr(ms.SQLiteMemoryBioRAG, "_epistemico_evaluar", _boom)
    with caplog.at_level(logging.WARNING, logger="BioRAG.MemoryStore"):
        res, total = cz.buscar_por_frase("manzana roja", limite=5)
    assert total >= 1 and len(res) >= 1  # ranking intacto pese al fallo
    assert any("epistemico" in r.message for r in caplog.records
               if r.name == "BioRAG.MemoryStore"), "sin rastro en log"

    # Puente DMN roto -> tambien deja rastro, no rompe
    monkeypatch.setattr(ms.SQLiteMemoryBioRAG, "_epistemico_evaluar",
                        ms.SQLiteMemoryBioRAG._epistemico_evaluar)
    import core.dmn_reflexion as dmn
    monkeypatch.setattr(dmn, "_guardar_estado",
                        lambda s: (_ for _ in ()).throw(IOError("disco lleno (simulado)")))
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="BioRAG.MemoryStore"):
        cz._epistemico_encolar_vacio("vacio con dmn roto", 0.05)
    assert any("encolar vacio DMN fallo" in r.message for r in caplog.records)
