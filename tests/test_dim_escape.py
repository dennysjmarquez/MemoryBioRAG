"""Fase B (resonancia dimensional): escape QCR calibrado para dim-coseno.

Regla: con BIORAG_DIM_ESCAPE=1, un candidato dimensional_fallback con
cobertura 0 sobrevive QCR si score_capa >= DIM_ESCAPE_T (0.45).
Calibracion: 40 negativos max 0.0 (sin candidatos dim); Q-01 0.488.
OFF = cortocircuito, path byte-identico.
"""
import inspect

import core.memory.constants as constants
import core.memory_store as ms
from core.memory_store import SQLiteMemoryBioRAG

Q = "quasar nebulosa pulsar"
QDIMS = list(range(1, 21))  # 20 dims


def _db(tmp_path, name):
    """Semilla FTS + V (shared 7/20, cos ~0.59: entre T y 0.60) + C
    (shared 4/20, cos ~0.447: bajo T). V y C sin tokens de Q."""
    c = SQLiteMemoryBioRAG(str(tmp_path / name))
    c.percibir_corto_plazo("fts_semilla", "quasar nebulosa pulsar")
    c.consolidar_concepto("fts_semilla")
    c.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, estado, peso_sinaptico) VALUES ('v_escape', 'relleno victima zzz yyy xxx', 'activo', 0.5)"
    )
    for d in range(1, 8):
        c.cursor.execute(
            "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES ('v_escape', ?)", (d,)
        )
    c.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, estado, peso_sinaptico) VALUES ('c_piso', 'relleno control www vvv uuu', 'activo', 0.5)"
    )
    for d in range(1, 5):
        c.cursor.execute(
            "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES ('c_piso', ?)", (d,)
        )
    c.conn.commit()
    return c


def _pool(c):
    return [r[1] for r in (c.last_todos or [])]


def test_flags_default():
    assert constants.DIM_ESCAPE is False
    assert constants.DIM_ESCAPE_T == 0.45


def test_enganche_en_qcr():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert 'constants.DIM_ESCAPE and origen_tipo == "dimensional_fallback"' in src


def test_off_remueve_on_rescata(tmp_path, monkeypatch):
    c = _db(tmp_path, "dime.db")
    monkeypatch.setattr(constants, "DIM_RESONANCIA", True)
    monkeypatch.setattr(constants, "DIM_ESCAPE", False)
    res_off, _ = c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    assert "v_escape" in _pool(c)
    assert "v_escape" not in [r[0] for r in res_off]
    monkeypatch.setattr(constants, "DIM_ESCAPE", True)
    res_on, _ = c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    assert "v_escape" in [r[0] for r in res_on]
    c.cerrar_sistema()


def test_piso_rechaza_bajo_t(tmp_path, monkeypatch):
    c = _db(tmp_path, "dime2.db")
    monkeypatch.setattr(constants, "DIM_RESONANCIA", True)
    monkeypatch.setattr(constants, "DIM_ESCAPE", True)
    res_on, _ = c.buscar_por_frase(Q, limite=5, dimensiones_ids=QDIMS)
    assert "c_piso" in _pool(c)
    assert "c_piso" not in [r[0] for r in res_on]
    c.cerrar_sistema()
