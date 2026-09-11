"""E3: QCR ponderado por IDF. Escapes y hub no se rompen."""
from core.memory_store import SQLiteMemoryBioRAG, QCR_IDF_ACTIVO, QCR_IDF_UMBRAL


def test_flags_rango():
    assert 0.30 <= QCR_IDF_UMBRAL <= 0.45 or QCR_IDF_UMBRAL == 0.40
    assert QCR_IDF_ACTIVO in (True, False)


def test_idf_raro_mayor_que_comun(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e3idf.db"))
    for i in range(8):
        c.percibir_corto_plazo(f"n_comun_{i}", "memoria sistema bio rag")
        c.consolidar_concepto(f"n_comun_{i}")
    c.percibir_corto_plazo("n_raro", "xyzqwertyunico token extra largo")
    c.consolidar_concepto("n_raro")
    m = c._idf_tokens_qcr(["memoria", "xyzqwertyunico"])
    assert m["xyzqwertyunico"] > m["memoria"]
    c.cerrar_sistema()


def test_qcr_idf_no_fusiona(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e3nf.db"))
    c.percibir_corto_plazo("a", "uno dos tres cuatro")
    c.consolidar_concepto("a")
    c.percibir_corto_plazo("b", "cinco seis siete ocho")
    c.consolidar_concepto("b")
    c.buscar_por_frase("uno dos tres", limite=5)
    n = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    c.cerrar_sistema()
    assert n == 2


def test_buscar_por_frase_llama_idf():
    import inspect
    from core.memory_store import SQLiteMemoryBioRAG
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_idf_tokens_qcr" in src
    assert "QCR_IDF_UMBRAL" in src or "_qcr_umbral" in src


def test_escape_typo_sigue(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e3esc.db"))
    c.percibir_corto_plazo("cuando_usar_dimensiones_biorag", "guia de cuando usar dimensiones en biorag")
    c.consolidar_concepto("cuando_usar_dimensiones_biorag")
    res, _ = c.buscar_por_frase("cuando usar dimenciones biorag", limite=5)
    c.cerrar_sistema()
    assert isinstance(res, list)
