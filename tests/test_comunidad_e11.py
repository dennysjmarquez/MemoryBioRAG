"""E11: comunidad_score LPA cacheado, O(1) por candidato."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG


def _nodo(c, name, txt):
    c.percibir_corto_plazo(name, txt)
    c.consolidar_concepto(name)


def test_misma_comunidad_si_arista(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "COMUNIDAD_PESO", 0.05)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e11.db"))
    _nodo(c, "nodo_a_e11", "contenido alfa tokenunicoaaa")
    _nodo(c, "nodo_b_e11", "contenido beta tokenunicobbb")
    c.cursor.execute("DELETE FROM sinapsis")
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
        "VALUES ('nodo_a_e11', 'nodo_b_e11', 0.8, 'test', 0)"
    )
    c.conn.commit()
    c._comunidad_map = None
    mp = c._asegurar_mapa_comunidades()
    assert mp["nodo_a_e11"] == mp["nodo_b_e11"]
    scores = c._comunidad_scores_pool(["nodo_a_e11"], ["nodo_a_e11", "nodo_b_e11", "ausente"])
    assert scores["nodo_a_e11"] == 1.0
    assert scores["nodo_b_e11"] == 1.0
    c.cerrar_sistema()


def test_peso_cero_vacio(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "COMUNIDAD_PESO", 0.0)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e11z.db"))
    assert c._comunidad_scores_pool(["x"], ["x", "y"]) == {}
    c.cerrar_sistema()


def test_hibrido_num_y_den():
    src = inspect.getsource(SQLiteMemoryBioRAG._calcular_score_hibrido)
    assert "COMUNIDAD_PESO" in src
    assert "comunidad_score" in src
    src2 = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_comunidad_scores_pool" in src2


def test_hibrido_sube_si_comunidad(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "COMUNIDAD_PESO", 0.05)
    c = SQLiteMemoryBioRAG.__new__(SQLiteMemoryBioRAG)
    s0 = SQLiteMemoryBioRAG._calcular_score_hibrido(c, bm25_norm=0.5, comunidad_score=0.0)
    s1 = SQLiteMemoryBioRAG._calcular_score_hibrido(c, bm25_norm=0.5, comunidad_score=1.0)
    assert s1 > s0
