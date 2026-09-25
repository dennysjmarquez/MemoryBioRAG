"""Fase A (resonancia dimensional): candidatura dim por merito, sin sesgo rowid.

Regla: con BIORAG_DIM_RESONANCIA=1, el fallback dimensional candidata con
GROUP BY + HAVING umbral + ORDER BY shared DESC, peso DESC, concepto ASC +
LIMIT K. El path viejo (LIMIT 500 sin ORDER BY + top-50 python) excluia
sistematicamente nodos recientes (los 3 golds EXP-Q pasaban el umbral pero
caian fuera de la ventana). OFF = path byte-identico.
"""
import inspect

import core.memory.constants as constants
import core.memory_store as ms
from core.memory_store import SQLiteMemoryBioRAG

Q = "quasar nebulosa pulsar"
QDIMS = list(range(1, 11))
N_RIVALES = 70


def _db(tmp_path, name):
    """1 semilla FTS (pool>=1 -> umbral 3) + 70 rivales (shared 8, peso 0.9,
    rowid bajo) + V (shared 10, peso 0.1, rowid alto, pares mas alla de 500).
    Rivales y V sin tokens de Q (invisibles a FTS/lexico)."""
    c = SQLiteMemoryBioRAG(str(tmp_path / name))
    c.percibir_corto_plazo("fts_semilla", "quasar nebulosa pulsar")
    c.consolidar_concepto("fts_semilla")
    for i in range(N_RIVALES):
        n = f"rival_{i:02d}"
        c.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, estado, peso_sinaptico) VALUES (?, ?, 'activo', 0.9)",
            (n, f"relleno rival numero {i} lorem ipsum dolor"),
        )
        for d in range(1, 9):
            c.cursor.execute(
                "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)", (n, d)
            )
    c.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, estado, peso_sinaptico) VALUES ('v_resonancia', 'relleno victima zzz yyy xxx', 'activo', 0.1)"
    )
    for d in range(1, 11):
        c.cursor.execute(
            "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES ('v_resonancia', ?)", (d,)
        )
    c.conn.commit()
    return c


def _pool(c):
    return [r[1] for r in (c.last_todos or [])]


def _dim_origenes(c):
    return [k for k, v in (c.last_origen_scores or {}).items() if v[0] == "dimensional_fallback"]


def test_flags_default():
    assert constants.DIM_RESONANCIA is False
    assert constants.DIM_RESONANCIA_K == 50


def test_enganche_en_fallback():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "if constants.DIM_RESONANCIA:" in src
    assert "GROUP_CONCAT(d.dimension_id)" in src


def test_off_excluye_on_incluye(tmp_path, monkeypatch):
    c = _db(tmp_path, "dimr.db")
    monkeypatch.setattr(constants, "DIM_RESONANCIA", False)
    c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    pool_off = _pool(c)
    assert "v_resonancia" not in pool_off
    assert len(pool_off) == 51  # 1 FTS + 50 rivales (top-50 python)
    monkeypatch.setattr(constants, "DIM_RESONANCIA", True)
    monkeypatch.setattr(constants, "DIM_RESONANCIA_K", 50)
    c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    pool_on = _pool(c)
    assert "v_resonancia" in pool_on  # merito: shared 10 > 8 pese a peso 0.1
    assert (c.last_origen_scores or {}).get("v_resonancia", (None,))[0] == "dimensional_fallback"
    assert len(_dim_origenes(c)) <= 50  # LIMIT K acota polucion
    c.cerrar_sistema()


def test_k1_solo_victima(tmp_path, monkeypatch):
    c = _db(tmp_path, "dimr2.db")
    monkeypatch.setattr(constants, "DIM_RESONANCIA", True)
    monkeypatch.setattr(constants, "DIM_RESONANCIA_K", 1)
    c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    pool = _pool(c)
    assert pool.count("v_resonancia") == 1
    assert _dim_origenes(c) == ["v_resonancia"]
    c.cerrar_sistema()
