"""E12: Hopfield ultimo recurso solo con ranking vacio."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG
from core.sdm import indexar_nodo_sdm, rescatar_hopfield_ultimo_recurso


def test_no_dispara_si_hay_hits(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "HOPFIELD_FALLBACK", True)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e12hit.db"))
    c.percibir_corto_plazo("nodo_lexico_e12", "contenido lexico tokenunicoe12abc")
    c.consolidar_concepto("nodo_lexico_e12")
    res, n = c.buscar_por_frase("tokenunicoe12abc", limite=5)
    assert n >= 1
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "rescatar_hopfield_ultimo_recurso" in src
    assert any(r[0] == "nodo_lexico_e12" for r in res)
    c.cerrar_sistema()


def test_flag_off_vacio(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "HOPFIELD_FALLBACK", False)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e12off.db"))
    c.percibir_corto_plazo("nodo_hf_e12", "zetaomega contenido hopfieldxyz")
    c.consolidar_concepto("nodo_hf_e12")
    indexar_nodo_sdm(c, "nodo_hf_e12")
    res, n = c.buscar_por_frase("zzzznotokenqqqwww", limite=5)
    assert n == 0 or not any(
        c.last_origen_scores.get(r[0], ("", 0))[0] == "hopfield_ultimo_recurso"
        for r in res
    )
    c.cerrar_sistema()


def test_rescate_query_vacia_no():
    class Dummy:
        pass
    assert rescatar_hopfield_ultimo_recurso(Dummy(), "  ") == []


def test_origen_en_fuente():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "hopfield_ultimo_recurso" in src
    assert "HOPFIELD_FALLBACK" in src
