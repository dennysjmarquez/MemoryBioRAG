"""E13: abstencion si top-1 bajo tau y origen no protegido."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG


def test_flag_en_fuente():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "METACOGNICION_ACTIVA" in src
    assert "sin_evidencia_directa" in src


def test_abstiene_score_bajo(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "METACOGNICION_ACTIVA", True)
    monkeypatch.setattr(ms, "METACOG_TAU", 0.99)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e13lo.db"))
    c.percibir_corto_plazo("nodo_ruido_e13", "contenido generico receta paella valenciana xyz")
    c.consolidar_concepto("nodo_ruido_e13")
    res, n = c.buscar_por_frase("receta paella valenciana", limite=5)
    assert n == 0
    assert res == []
    assert c.last_estado_epistemico.get("estado") == "sin_evidencia_directa"
    c.cerrar_sistema()


def test_flag_off_no_abstiene(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "METACOGNICION_ACTIVA", False)
    monkeypatch.setattr(ms, "METACOG_TAU", 0.99)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e13off.db"))
    c.percibir_corto_plazo("nodo_keep_e13", "contenido keep tokenkeepe13xyz")
    c.consolidar_concepto("nodo_keep_e13")
    res, n = c.buscar_por_frase("tokenkeepe13xyz", limite=5)
    assert n >= 1
    c.cerrar_sistema()
