"""E7: JSD adaptativo por longitud de query (Nt tokens >= 3)."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG, JSD_ADAPT_BASE


def test_query_larga_boost(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "JSD_ADAPTATIVO", True)
    monkeypatch.setattr(ms, "JSD_WEIGHT", 0.0)
    w = SQLiteMemoryBioRAG._jsd_weight_adaptativo("uno dos tres cuatro cinco")
    assert abs(w - JSD_ADAPT_BASE * 2.5) < 1e-9


def test_query_corta_protege(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "JSD_ADAPTATIVO", True)
    monkeypatch.setattr(ms, "JSD_WEIGHT", 0.0)
    w = SQLiteMemoryBioRAG._jsd_weight_adaptativo("boost")
    assert abs(w - JSD_ADAPT_BASE * 0.5) < 1e-9


def test_flag_off_usa_estatico(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "JSD_ADAPTATIVO", False)
    monkeypatch.setattr(ms, "JSD_WEIGHT", 0.0)
    assert SQLiteMemoryBioRAG._jsd_weight_adaptativo("uno dos tres cuatro cinco") == 0.0


def test_hibrido_respeta_jsd_weight(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e7.db"))
    s0 = c._calcular_score_hibrido(bm25_norm=0.5, jsd_score=1.0, jsd_weight=0.0)
    s1 = c._calcular_score_hibrido(bm25_norm=0.5, jsd_score=1.0, jsd_weight=0.125)
    c.cerrar_sistema()
    assert s1 > s0


def test_fuente_buscar():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_jsd_weight_adaptativo" in src
    assert "_jsd_w_e7" in src
