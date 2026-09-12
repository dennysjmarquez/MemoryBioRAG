"""F5: campo semántico contextual PPMI (Plan Maestro, INVENCIÓN 3).

Φ(c) = gauss(c,q) + Σ gauss(c,k). Vectores INYECTADOS (100-dim):
el SVD tiny no es evidencia. Normalización a norma unidad dentro.
"""
import numpy as np
import pytest

from core.memory_store import SQLiteMemoryBioRAG, CAMPO_POTENCIAL_PESO
from core.ppmi_hybrid_search import calcular_campo_potencial_ppmi


def _v(*coords):
    v = np.zeros(100)
    for i, x in enumerate(coords):
        v[i] = x
    return v


class _Stub:
    def __init__(self, vecs):
        self._ppmi_index = type("I", (), {"vecs": vecs})()


def _cluster():
    # Cluster a,b,c cerca de (1,0); z outlier en (0,1); q=(1,0).
    return _Stub({
        "a": _v(1, 0), "b": _v(1, 0.1), "c": _v(0.9, 0.05),
        "z": _v(0, 1),
    }), _v(1, 0), ["a", "b", "c", "z"]


def test_cluster_supera_outlier():
    stub, q, pool = _cluster()
    out = calcular_campo_potencial_ppmi(stub, q, pool, sigma=1.0)
    assert set(out) == set(pool)
    assert all(0.0 <= v <= 1.0 for v in out.values())
    assert max(out, key=out.get) in {"a", "b", "c"}  # el centro denso gana
    assert out["a"] > 0.9 and out["b"] > 0.9 and out["c"] > 0.9
    assert out["z"] < 0.6  # outlier: solo colas gaussianas


def test_query_atrae():
    stub = _Stub({"m": _v(1, 0), "n": _v(-1, 0)})
    out = calcular_campo_potencial_ppmi(stub, _v(1, 0), ["m", "n"], sigma=1.0)
    assert out["m"] > out["n"]
    assert out["m"] == pytest.approx(1.0)


def test_vacio_seguro():
    stub, q, _ = _cluster()
    assert calcular_campo_potencial_ppmi(stub, q, [], sigma=1.0) == {}
    assert calcular_campo_potencial_ppmi(stub, q, ["a"], sigma=0.0) == {}
    assert calcular_campo_potencial_ppmi(stub, q, ["a"], sigma=-2.0) == {}
    assert calcular_campo_potencial_ppmi(object(), q, ["a"], sigma=1.0) == {}
    assert calcular_campo_potencial_ppmi(_Stub({}), q, ["a"], sigma=1.0) == {}
    # Query None: solo densidad pool, no explota.
    out = calcular_campo_potencial_ppmi(stub, None, ["a", "b"], sigma=1.0)
    assert set(out) == {"a", "b"}


def test_sin_vector_cero():
    stub, q, _ = _cluster()
    out = calcular_campo_potencial_ppmi(stub, q, ["a", "fantasma"], sigma=1.0)
    assert out["fantasma"] == 0.0
    assert out["a"] == pytest.approx(1.0)


def test_sigma_afina():
    stub, q, pool = _cluster()
    gordo = calcular_campo_potencial_ppmi(stub, q, pool, sigma=1.0)
    fino = calcular_campo_potencial_ppmi(stub, q, pool, sigma=0.01)
    assert gordo["b"] > 0.5   # σ=1: el cluster se corrobora
    assert fino["b"] < 0.01   # σ→0: solo sobrevive el casi-idéntico a q
    assert fino["a"] == pytest.approx(1.0)


def test_peso_default_on_tras_gate():
    assert CAMPO_POTENCIAL_PESO == 0.05


def test_integracion_buscar(tmp_path, monkeypatch):
    import core.memory_store as ms
    from core.ppmi_hybrid_search import IndicesBioRAG
    from core.ppmi_vectorizer import reindexar_ppmi_svd
    monkeypatch.setattr(ms, "CAMPO_POTENCIAL_PESO", 0.05)
    c = SQLiteMemoryBioRAG(str(tmp_path / "f5.db"))
    for name, txt in (
        ("fldA", "campo magnetico alfa xyzcampo"),
        ("fldB", "campo magnetico beta xyzcampo"),
        ("fldC", "otro tema nada que ver"),
    ):
        c.percibir_corto_plazo(name, txt)
        c.consolidar_concepto(name)
    reindexar_ppmi_svd(c.conn)
    c._ppmi_index = IndicesBioRAG(str(tmp_path / "f5.db"))
    c._ppmi_index.vecs = {
        "flda": _v(1, 0), "fldb": _v(1, 0.1), "fldc": _v(0, 1),
    }
    r, _total = c.buscar_por_frase("xyzcampo campo magnetico")
    names = [x[0] for x in r]
    assert "flda" in names and "fldb" in names  # cableado: no explota, rankea
