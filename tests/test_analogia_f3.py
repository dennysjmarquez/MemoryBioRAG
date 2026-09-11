"""F3: analogia relacional simbolica A:B :: C:D por algebra PPMI local.

Vectores INYECTADOS en idx.vecs (fallback aprobado): el corpus tiny/SVD
no es evidencia de la aritmetica. 100-dim como DIM_VECTORIAL.
"""
import numpy as np
import pytest

from core.memory_store import SQLiteMemoryBioRAG, ANALOGIA_PESO, ANALOGIA_DETECTAR
from core.ppmi_hybrid_search import (
    detectar_analogia,
    resolver_analogia_simbolica,
)


def _v(*coords):
    v = np.zeros(100)
    for i, x in enumerate(coords):
        v[i] = x
    return v


class _Stub:
    def __init__(self, vecs):
        self._ppmi_index = type("I", (), {"vecs": vecs})()


def test_aritmetica_pura():
    # a=(1,0) b=(1,1) c=(0,0) -> v=(0,1); d=(0,1) debe rankear 1.0
    stub = _Stub({
        "a": _v(1, 0), "b": _v(1, 1), "c": _v(0, 0),
        "d": _v(0, 1), "ruido": _v(0, -1),
    })
    res = resolver_analogia_simbolica(stub, "a", "b", "c", limite=5)
    assert res[0][0] == "d"
    assert res[0][1] == pytest.approx(1.0)
    names = [r[0] for r in res]
    assert "a" not in names and "b" not in names and "c" not in names


def test_falta_vector_devuelve_vacio():
    stub = _Stub({"a": _v(1, 0), "c": _v(0, 0)})
    assert resolver_analogia_simbolica(stub, "a", "b", "c") == []
    assert resolver_analogia_simbolica(_Stub({}), "a", "b", "c") == []
    assert resolver_analogia_simbolica(object(), "a", "b", "c") == []


def test_deteccion_sintaxis():
    assert detectar_analogia("rey es a hombre como reina es a ?") == ("rey", "hombre", "reina")
    assert detectar_analogia("rey es a hombre como reina qué es") == ("rey", "hombre", "reina")
    assert detectar_analogia("como rey es a hombre, qué es reina") == ("rey", "hombre", "reina")
    assert detectar_analogia("quien creo biorag") is None
    assert detectar_analogia("") is None
    assert detectar_analogia(None) is None


def test_default_off():
    assert ANALOGIA_PESO == 0.0
    assert ANALOGIA_DETECTAR is False


def _cerebro_con_vecs(tmp_path):
    from core.ppmi_hybrid_search import IndicesBioRAG
    from core.ppmi_vectorizer import reindexar_ppmi_svd
    c = SQLiteMemoryBioRAG(str(tmp_path / "f3.db"))
    for name, txt in (
        ("anclaA", "nodo alfa primero"),
        ("anclaB", "nodo beta segundo"),
        ("anclaC", "nodo gamma tercero"),
        ("anclaD", "nodo delta cuarto anclaA anclaB anclaC"),
    ):
        c.percibir_corto_plazo(name, txt)
        c.consolidar_concepto(name)
    # Tablas tokens/nodos solo existen tras reindex (sueño). Indice real,
    # pero vecs FAKE inyectados: el SVD tiny no es evidencia.
    reindexar_ppmi_svd(c.conn)
    c._ppmi_index = IndicesBioRAG(str(tmp_path / "f3.db"))
    c._ppmi_index.vecs = {
        "anclaa": _v(1, 0), "anclab": _v(1, 1),
        "anclac": _v(0, 0), "anclad": _v(0, 1),
    }
    return c


def test_scores_pool_metodo(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "ANALOGIA_PESO", 0.05)
    c = _cerebro_con_vecs(tmp_path)
    vt = _v(0, 1)  # = vec(C) + (vec(B) - vec(A))
    m = c._analogia_scores_pool(vt, ["anclaa", "anclab", "anclac", "anclad", "fantasma"])
    assert m["anclad"] == pytest.approx(1.0)
    assert m["anclaa"] == pytest.approx(0.0)
    assert m["fantasma"] == 0.0


def test_peso_cero_devuelve_vacio(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "ANALOGIA_PESO", 0.0)
    c = _cerebro_con_vecs(tmp_path)
    assert c._analogia_scores_pool(_v(0, 1), ["anclaD"]) == {}


def test_integracion_buscar_analogia(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "ANALOGIA_PESO", 0.05)
    c = _cerebro_con_vecs(tmp_path)
    r, _total = c.buscar_por_frase("anclaA es a anclaB como anclaC es a ?", analogia=True)
    names = [x[0] for x in r]
    assert "anclad" in names  # entra al pool por contenido; analogia lo puntua
    # Sin flag analogia y DETECTAR=0: mismo camino que antes (no explota).
    r2, _ = c.buscar_por_frase("anclaA es a anclaB como anclaC es a ?")
    assert isinstance(r2, list)


def test_servicio_resolver_analogia(tmp_path):
    from core.memory_service import resolver_analogia
    c = _cerebro_con_vecs(tmp_path)
    res = resolver_analogia(c, "anclaA", "anclaB", "anclaC", limite=3)
    assert res[0][0] == "anclad"
    assert len(res) <= 3
