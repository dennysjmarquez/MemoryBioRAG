"""E6: NCD zlib como senal de scoring O(k) sobre el pool."""
from core.memory_store import SQLiteMemoryBioRAG, NCD_PESO


def test_ncd_identidad_alta():
    s = SQLiteMemoryBioRAG._ncd_sim("el gato negro duerme", "el gato negro duerme")
    assert s >= 0.85


def test_ncd_textos_distintos_menor():
    a = SQLiteMemoryBioRAG._ncd_sim(
        "mamifero domestico felidae gato minino",
        "mamifero domestico felidae gato minino extra",
    )
    b = SQLiteMemoryBioRAG._ncd_sim(
        "mamifero domestico felidae gato minino",
        "servidor http timeout conexion red kernel panic",
    )
    assert a > b


def test_ncd_solo_pool(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e6.db"))
    c.percibir_corto_plazo("alpha_nodo", "mamifero domestico felidae gato minino")
    c.consolidar_concepto("alpha_nodo")
    c.percibir_corto_plazo("omega_nodo", "servidor http timeout conexion red")
    c.consolidar_concepto("omega_nodo")
    sims = c._ncd_sims_pool("mamifero domestico felidae", [("alpha_nodo", "mamifero domestico felidae gato minino")])
    assert "alpha_nodo" in sims
    assert "omega_nodo" not in sims
    n = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    assert n == 2
    c.cerrar_sistema()


def test_formula_suma_ncd(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e6f.db"))
    s0 = c._calcular_score_hibrido(bm25_norm=0.5, ncd_score=0.0)
    s1 = c._calcular_score_hibrido(bm25_norm=0.5, ncd_score=1.0)
    c.cerrar_sistema()
    if NCD_PESO > 0:
        assert s1 > s0
    else:
        assert s1 == s0


def test_fuente_buscar():
    import inspect
    from core.memory_store import SQLiteMemoryBioRAG
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_ncd_sims_pool" in src
    assert "ncd_score" in src
    src_h = inspect.getsource(SQLiteMemoryBioRAG._calcular_score_hibrido)
    assert "NCD_PESO * ncd_score" in src_h
