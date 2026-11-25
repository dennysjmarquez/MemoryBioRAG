"""Paso 1 «ojos Unicode»: palabras chinas/japonesas de 1–2 caracteres en la búsqueda.

Antes del cambio, `buscar_por_frase("番茄")` devolvía 0 aunque un recuerdo dijera
«今晚我炒蒜和番茄配米饭» (el trigram no busca < 3 caracteres y unicode61 toma la corrida
CJK entera como una palabra). Evidencia: docs/Mi neurona en el sistema/ojos_unicode_busqueda/.
Base sintética en tmp; nunca la DB viva ni el snapshot.
"""
from unittest.mock import patch

import pytest

from core.memory import cjk_corto

RELOJ = 1_793_059_200.0
MUNDO = [
    ("晚餐食谱一", "今晚我炒蒜和番茄配米饭。"),
    ("晚餐食谱二", "今天烤了番薯和土豆当晚饭。"),
    ("通勤メモ", "今日は電車が遅れて会社に遅刻した。"),
    ("通勤メモ二", "電話で上司に遅刻を伝えた。"),
    ("家の記録", "朝ごはんの後で猫が窓辺で寝ていた。"),
    ("receta_sopa", "La sopa de tomate lleva ajo y albahaca fresca."),
]
AJENOS = [(f"ajeno_{i}", t) for i, t in enumerate(
    ["妈妈在厨房做饺子。", "图书馆里非常安静。", "駅の近くに本屋がある。", "コーヒーを一杯飲んだ。",
     "El museo abre los domingos.", "The river flooded last spring."])]


@pytest.mark.parametrize("consulta,esperado", [
    ("番茄", ("番茄",)), ("猫", ("猫",)), ("パン", ("パン",)), ("ﾊﾟﾝ", ("パン",)),
    ("receta 番茄", ("番茄",)), ("番茄 番茄", ("番茄",)),
    ("の", ()), ("番茄配米饭", ()), ("tomate", ()), ("사과", ()), ("чай", ()), ("", ()),
])
def test_terminos_solo_corridas_cjk_cortas(consulta, esperado):
    assert cjk_corto.terminos(consulta) == esperado


def test_cobertura_depende_solo_del_recuerdo():
    a = cjk_corto.cobertura(("番茄",), "晚餐", "炒蒜和番茄", "", "")
    assert a > 0
    assert cjk_corto.cobertura(("番茄",), "晚餐", "烤了番薯", "", "") == 0.0
    assert cjk_corto.cobertura(("番茄",), "番茄", "炒蒜和番茄", "", "") > a  # también en el concepto


def _top(db, q):
    res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
    return [r[0] for r in res]


def _crear(tmp_path, nombre, recuerdos, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    from core.memory_service import aprender
    from core.memory_store import SQLiteMemoryBioRAG
    path = str(tmp_path / nombre)
    monkeypatch.setenv("BIORAG_PATH", path)
    db = SQLiteMemoryBioRAG(path)
    for c, t in recuerdos:
        aprender(db, c, t, consolidar=True)
    db.conn.commit()
    return db


def test_palabra_corta_en_medio_de_la_corrida(tmp_path, monkeypatch):
    with patch("time.time", return_value=RELOJ):
        db = _crear(tmp_path, "m.db", MUNDO, monkeypatch)
        try:
            assert _top(db, "番茄")[:1] == ["晚餐食谱一"]
            assert "晚餐食谱二" not in _top(db, "番茄")    # comparte solo 番
            assert _top(db, "電車")[:1] == ["通勤メモ"]
            assert "通勤メモ二" not in _top(db, "電車")    # comparte solo 電
            assert _top(db, "猫")[:1] == ["家の記録"]
            assert _top(db, "钢琴") == []                  # no aparece en ningún recuerdo
        finally:
            db.cerrar_sistema()


def test_sin_cjk_corto_el_fallback_no_se_ejecuta(tmp_path, monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("el fallback CJK no debe correr sin términos CJK cortos")
    with patch("time.time", return_value=RELOJ):
        db = _crear(tmp_path, "m.db", MUNDO, monkeypatch)
        try:
            with patch.object(cjk_corto, "filas", prohibido):
                assert _top(db, "tomate")[:1] == ["receta_sopa"]
                assert _top(db, "番茄配米饭")[:1] == ["晚餐食谱一"]
        finally:
            db.cerrar_sistema()


def test_invariante_a_recuerdos_ajenos(tmp_path, monkeypatch):
    with patch("time.time", return_value=RELOJ):
        a = _crear(tmp_path, "a.db", MUNDO, monkeypatch)
        try:
            antes = {q: _top(a, q) for q in ("番茄", "電車", "猫")}
        finally:
            a.cerrar_sistema()
        b = _crear(tmp_path, "b.db", MUNDO + AJENOS, monkeypatch)
        try:
            despues = {q: _top(b, q) for q in ("番茄", "電車", "猫")}
        finally:
            b.cerrar_sistema()
    assert antes == despues
