"""Graduación del bono de sinónimos: rareza del alias × posición en la lista.

POR QUÉ estas pruebas: el bono del piso de sinónimos (scoring.py) empujaba por
igual a todo nodo que declaraba la palabra, así que con el corpus grande decidía
BM25 y ganaba quien llevaba la palabra en el NOMBRE. Medido en la base viva
(1357 nodos): 17 nodos declaran «perfil» y los 17 puntuaban 1.0 en la señal.

Lo que se fija aquí es el contrato mínimo: la calidad vale 1.0 para el alias
mejor escrito (primera posición, sin datos de corpus), baja con la posición, y
NUNCA deja en cero una coincidencia real.
"""
import pytest

from core.fallback_simbolico import aliases_de, calidad_sinonimo


def test_aliases_parte_por_los_cuatro_separadores():
    assert aliases_de("perfil,ingeniero,explorador") == ["perfil", "ingeniero", "explorador"]
    assert aliases_de("a; b| c\nd") == ["a", "b", "c", "d"]
    assert aliases_de("") == []
    assert aliases_de("  ,  , ") == []


def test_sin_datos_de_corpus_solo_decide_la_posicion():
    assert calidad_sinonimo({"perfil"}, "perfil,ingeniero,explorador") == pytest.approx(1.0)
    # posición 2 de 5 con decaimiento 0.25 -> 1/(1+0.25) = 0.8
    assert calidad_sinonimo({"perfil"}, "notebooklm, perfil, dennys, id, cuaderno") == pytest.approx(0.8)


def test_alias_raro_vale_mas_que_alias_comun():
    df = {"perfil": 17}
    comun = calidad_sinonimo({"perfil"}, "perfil,ingeniero", df, 1357)
    raro = calidad_sinonimo({"perfil"}, "perfil,ingeniero", {"perfil": 1}, 1357)
    assert raro > comun
    assert 0.0 < comun < 1.0


def test_no_coincidir_es_cero():
    assert calidad_sinonimo({"zzz"}, "perfil,ingeniero") == 0.0
    assert calidad_sinonimo({"perfil"}, "") == 0.0
    assert calidad_sinonimo(set(), "perfil") == 0.0


def test_acentos_y_mayusculas_no_rompen_la_coincidencia():
    assert calidad_sinonimo({"metodologia"}, "Metodología,estandar-calidad") > 0.0


def test_sin_bandera_el_bono_no_cambia():
    """Con calidad=1.0 el score es EXACTAMENTE el de antes de este cambio."""
    from core.memory_store import SQLiteMemoryBioRAG

    kw = dict(bm25_norm=0.2, sinonimos_ratio=1.0, ppmi_score=0.3)
    db = SQLiteMemoryBioRAG.__new__(SQLiteMemoryBioRAG)  # sin abrir DB
    sin_pasar = db._calcular_score_hibrido(**kw)
    con_uno = db._calcular_score_hibrido(**kw, sinonimos_calidad=1.0)
    assert sin_pasar == con_uno


def test_calidad_baja_el_bono_pero_no_lo_elimina():
    from core.memory_store import SQLiteMemoryBioRAG

    db = SQLiteMemoryBioRAG.__new__(SQLiteMemoryBioRAG)
    kw = dict(bm25_norm=0.2, sinonimos_ratio=1.0, ppmi_score=0.3)
    pleno = db._calcular_score_hibrido(**kw, sinonimos_calidad=1.0)
    mitad = db._calcular_score_hibrido(**kw, sinonimos_calidad=0.5)
    assert mitad < pleno, "un alias peor escrito tiene que puntuar menos"
    assert mitad > 0.0, "pero sigue siendo una coincidencia real"
