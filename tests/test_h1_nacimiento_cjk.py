"""H1: las reglas de nacimiento de sinapsis ven chino y japonés (bigramas Unicode), sin cambiar nada
en textos sin escritura CJK. Evidencia: docs/Mi neurona en el sistema/neurona_sinaptica_estrella/h1_nacimiento_cjk/
"""
import re

import pytest

from core import cjk_unidades
from core.sinapsis import _TOKEN_PATTERN, _CORTO_PATTERN, TOKENS_TECNICOS_CORTOS, _tokenizar, auto_vincular
from core.stopwords import STOPWORDS
from core.memory_store import SQLiteMemoryBioRAG


TEXTOS_SIN_CJK = [
    "La consolidación de memoria ocurre durante el sueño profundo con ondas lentas",
    "The quick brown fox jumps over the lazy dog near the riverbank",
    "API_REST con cpu y ram: configurar el servidor MCP y la db",
    "Ünïcödé façade naïve — Привет мир, Γειά σου κόσμε, 안녕하세요 세계",
    "",
    "1234 5678 !!! ???",
]


def _tokenizar_antes(texto):
    """Copia literal de `_tokenizar` antes de H1."""
    texto = texto.replace('_', ' ')
    tokens = set(_TOKEN_PATTERN.findall(texto.lower()))
    tokens |= TOKENS_TECNICOS_CORTOS & set(_CORTO_PATTERN.findall(texto.lower()))
    return tokens - STOPWORDS


@pytest.mark.parametrize("texto", TEXTOS_SIN_CJK)
def test_sin_cjk_el_tokenizador_de_nacimiento_queda_identico(texto):
    assert cjk_unidades.unidades(texto) == set()
    assert cjk_unidades.sin_cjk(texto) == texto
    assert cjk_unidades.trigramas_fts(texto) == []
    assert _tokenizar(texto) == _tokenizar_antes(texto)


@pytest.mark.parametrize("texto", TEXTOS_SIN_CJK)
def test_sin_cjk_la_regla_del_sueno_queda_identica(texto):
    antes = set(re.findall(r'\w{4,}', texto.lower()))
    despues = set(re.findall(r'\w{4,}', cjk_unidades.sin_cjk(texto).lower())) | cjk_unidades.unidades(texto)
    assert despues == antes


def test_chino_se_parte_en_bigramas():
    assert cjk_unidades.unidades("今晚我炒番茄") == {"今晚", "晚我", "我炒", "炒番", "番茄"}
    assert {"番茄", "米饭"} <= _tokenizar("今晚我炒蒜和番茄配米饭")


def test_japones_omite_bigramas_solo_hiragana_y_hiragana_suelto():
    u = cjk_unidades.unidades("東京で寿司を食べている")
    assert "東京" in u and "寿司" in u
    assert "てい" not in u and "いる" not in u  # gramática: solo hiragana
    assert "で寿" in u  # mixto: cuenta
    assert cjk_unidades.unidades("の") == set()
    assert cjk_unidades.unidades("庭") == {"庭"}
    assert cjk_unidades.unidades("テ") == {"テ"}


def test_texto_mixto_separa_latin_y_cjk():
    t = "Python中文処理library"
    assert cjk_unidades.sin_cjk(t) == "Python    library"
    assert "python" in _tokenizar(t) and "library" in _tokenizar(t)
    assert {"中文", "文処", "処理"} <= _tokenizar(t)


def test_nfkc_y_trigramas_acotados():
    assert cjk_unidades.unidades("ﾃｽﾄ") == cjk_unidades.unidades("テスト")  # halfwidth → fullwidth
    largo = "東京大学の研究者が新しい材料を開発した" * 5
    tri = cjk_unidades.trigramas_fts(largo)
    assert 0 < len(tri) <= cjk_unidades.MAX_TRIGRAMAS_FTS
    assert all(len(g) == 3 for g in tri)


def _cerebro(tmp_path):
    return SQLiteMemoryBioRAG(db_path=str(tmp_path / "h1.db"))


def _guardar_largo(cer, concepto, contenido):
    cer.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, estado, peso_sinaptico) VALUES (?, ?, 'activo', 0.5)",
        (concepto, contenido))
    cer.conn.commit()


def test_auto_vincular_nace_sinapsis_entre_frases_chinas_relacionadas(tmp_path):
    cer = _cerebro(tmp_path)
    try:
        _guardar_largo(cer, "receta_a", "番茄炒蛋需要新鲜番茄和鸡蛋")
        _guardar_largo(cer, "ajeno", "足球比赛在周末举行")
        v = auto_vincular(cer, "receta_b", "新鲜番茄和鸡蛋做番茄炒蛋", umbral=0.4)
        destinos = {d for d, _ in v}
        assert "receta_a" in destinos
        assert "ajeno" not in destinos
    finally:
        cer.cerrar_sistema()


def test_auto_vincular_no_une_frases_japonesas_que_solo_comparten_gramatica(tmp_path):
    cer = _cerebro(tmp_path)
    try:
        _guardar_largo(cer, "a", "彼はサッカーをしている")
        v = auto_vincular(cer, "b", "私は料理をしている", umbral=0.4)
        assert v == []
    finally:
        cer.cerrar_sistema()
