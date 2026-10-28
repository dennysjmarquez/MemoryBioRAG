"""B4a: límite por prefijo o anterior W/F, sin listas de idiomas."""

import pytest

from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture(scope="module")
def cerebro():
    db = SQLiteMemoryBioRAG(":memory:")
    yield db
    db.cerrar_sistema()


@pytest.mark.parametrize("token,texto,esperado", [
    ("play", "displayed", 0),
    ("lay", "displayed", 0),
    ("play", "we play chess", 1),
    ("react", "reactive systems", 1),
    ("pan", "pan de centeno", 1),
    ("pan", "empanada", 0),
    ("мост", "старый мост", 1),
    ("мост", "мостовой", 1),
    ("항구", "비 오는 항구를 적었다.", 1),
    ("바다", "푸른 바다새", 1),
    ("黑麦面粉", "烘焙面包使用黑麦面粉。", 1),
    ("全粒粉", "手作りのパンには全粒粉を使った。", 1),
    ("ラス", "ガラス", 1),
    ("ＢＣ", "ＡＢＣ", 1),
    ("２３", "１２３４", 1),
    ("哈哈", "x哈哈哈", 1),  # Las coincidencias se pueden solapar.
    ("", "texto", 0),
    ("texto", None, 0),
    (None, "texto", 0),
])
def test_palabra_inicio_ancho_sqlite(cerebro, token, texto, esperado):
    (valor,) = cerebro.conn.execute("SELECT PALABRA_INICIO_ANCHO(?, ?)", (token, texto)).fetchone()
    assert valor == esperado


def test_prefijo_original_y_predicados_no_se_sustituyen(cerebro):
    nuevo, anterior = cerebro.conn.execute(
        "SELECT PALABRA_INICIO_ANCHO(?, ?), PALABRA_PREFIJO(?, ?)",
        ("全粒粉", "パンには全粒粉", "全粒粉", "パンには全粒粉"),
    ).fetchone()
    assert (nuevo, anterior) == (1, 0)


def test_no_se_invierte_consulta_mayor_que_campo(cerebro):
    (valor,) = cerebro.conn.execute(
        "SELECT PALABRA_INICIO_ANCHO(?, ?)", ("海岸灯塔是什么意思", "海岸灯塔")
    ).fetchone()
    assert valor == 0


def test_normalizacion_compartida_sigue_pendiente(cerebro):
    con_marca, sin_marca = cerebro.conn.execute(
        "SELECT PALABRA_INICIO_ANCHO(?, ?), PALABRA_INICIO_ANCHO(?, ?)",
        ("ガ", "カ\u3099ラス", "カ", "カ\u3099ラス"),
    ).fetchone()
    assert (con_marca, sin_marca) == (0, 1)
