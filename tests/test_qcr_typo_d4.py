"""Fase 1 (F-QCR-D4): segunda oportunidad QCR tolerante a typos (all-near).

Regla: con BIORAG_QCR_TYPO=1, un candidato con score >= piso (0.35) que
falla cobertura exacta sobrevive si CADA token tiene hit exacto o
near-match (lev<=2, len>=4). Calibrado 19/19: rescata Clase-A 4/4,
0/14 distractores, 0738 a salvo.
"""
import inspect

import core.memory.constants as constants
import core.memory_store as ms
from core.memory_store import (
    SQLiteMemoryBioRAG,
    _qcr_levenshtein,
    _qcr_todos_cercanos,
)

QUERY = "alfa betay gamme delta"


def _db(tmp_path, name):
    """AND=0 (nadie tiene los 4) -> fallback trae parciales.
    C: 3/4 exactos (pasa QCR; evita no-op de filtrados vacio).
    A: 1/4 exactos ('alfa' -> entra por OR literal SIN escape),
       4/4 near-or-hit (victima rescatable solo si ON).
    D: 1/4 exactos, 1 near + 3 far (control: ausente aun si ON)."""
    c = SQLiteMemoryBioRAG(str(tmp_path / name))
    c.percibir_corto_plazo("c_topico_qcr", "alfa betay gamme")
    c.consolidar_concepto("c_topico_qcr")
    c.percibir_corto_plazo("a_topico_qcr", "alfa beta gamma delt")
    c.consolidar_concepto("a_topico_qcr")
    c.percibir_corto_plazo("d_topico_qcr", "alfa zetauno zetados")
    c.consolidar_concepto("d_topico_qcr")
    return c


def _score_por_concepto(monkeypatch, mapa):
    def fake(self, *a, **k):
        loc = inspect.currentframe().f_back.f_locals
        return mapa.get(loc.get("concepto"), 0.1)
    monkeypatch.setattr(SQLiteMemoryBioRAG, "_calcular_score_hibrido", fake)


def test_flags_default():
    # Shipped ON: gate Fase 1 pasado (98.06/17/FP0). OFF solo por entorno.
    assert constants.QCR_TYPO_ACTIVA is True
    assert constants.QCR_TYPO_PISO == 0.35
    assert constants.QCR_TYPO_DIST == 2


def test_enganche_en_qcr():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "constants._qcr_todos_cercanos(q_tokens_qcr, text_target, constants.QCR_TYPO_DIST)" in src


def test_levenshtein():
    assert _qcr_levenshtein("test", "test") == 0
    assert _qcr_levenshtein("tests", "test") == 1
    assert _qcr_levenshtein("tcenico", "tecnico") == 2
    assert _qcr_levenshtein("bioraig", "biorag") == 1
    assert _qcr_levenshtein("ponytailhelp", "leccion") > 2
    assert _qcr_levenshtein("abc", "abcdefghijk") > 2


def test_todos_cercanos_casos():
    assert _qcr_todos_cercanos(["alfa", "beta"], "alfa beta gamma") is True
    assert _qcr_todos_cercanos(["gamme"], "gamma delta") is True
    assert _qcr_todos_cercanos(["gamme", "zzzqqq"], "gamma delta") is False
    # token corto: solo exacto ('moe' no se acerca a 'de')
    assert _qcr_todos_cercanos(["moe"], "de biorag alfa") is False
    assert _qcr_todos_cercanos(["moe"], "moe biorag alfa") is True
    # '_' parte palabras ('tests' ~ 'test' dentro de concepto)
    assert _qcr_todos_cercanos(["tests"], "cv_seccion_d_test_vinculacion") is True
    assert _qcr_todos_cercanos([], "cualquier texto") is True
    assert _qcr_todos_cercanos(["gamma"], "") is False


def test_todos_cercanos_caso_0733():
    # Regresion calibracion: 'bioraig'~'biorag' pero 'moe' corto sin exacto
    assert _qcr_todos_cercanos(
        ["pan", "moe", "bioraig"], "pan de biorag expansion") is False


def test_off_remueve_on_rescata(tmp_path, monkeypatch):
    c = _db(tmp_path, "d4.db")
    _score_por_concepto(monkeypatch, {
        "a_topico_qcr": 0.9, "c_topico_qcr": 0.8, "d_topico_qcr": 0.9})
    monkeypatch.setattr(constants, "QCR_TYPO_ACTIVA", False)
    res_off, _ = c.buscar_por_frase(QUERY, limite=5)
    dev_off = [r[0] for r in res_off]
    pool_off = [r[1] for r in (c.last_todos or [])]
    assert "c_topico_qcr" in dev_off
    assert "a_topico_qcr" in pool_off
    assert "a_topico_qcr" not in dev_off
    monkeypatch.setattr(constants, "QCR_TYPO_ACTIVA", True)
    res_on, _ = c.buscar_por_frase(QUERY, limite=5)
    dev_on = [r[0] for r in res_on]
    assert "c_topico_qcr" in dev_on
    assert "a_topico_qcr" in dev_on
    assert "d_topico_qcr" not in dev_on
    c.cerrar_sistema()


def test_piso_respeta_bajo_umbral(tmp_path, monkeypatch):
    c = _db(tmp_path, "d4b.db")
    _score_por_concepto(monkeypatch, {
        "a_topico_qcr": 0.20, "c_topico_qcr": 0.8, "d_topico_qcr": 0.1})
    monkeypatch.setattr(constants, "QCR_TYPO_ACTIVA", True)
    res, _ = c.buscar_por_frase(QUERY, limite=5)
    dev = [r[0] for r in res]
    assert "a_topico_qcr" not in dev
    c.cerrar_sistema()
