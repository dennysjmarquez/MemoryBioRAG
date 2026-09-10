"""E2: SDM como señal de scoring sobre el pool (O(k), no O(N))."""
from core.memory_store import SQLiteMemoryBioRAG, SDM_SCORING_PESO
from core.sdm import indexar_nodo_sdm, similitudes_sdm_pool


def test_similitudes_solo_pool_no_corpus(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e2.db"))
    c.percibir_corto_plazo("alpha_nodo", "mamifero domestico felidae gato minino")
    c.consolidar_concepto("alpha_nodo")
    c.percibir_corto_plazo("omega_nodo", "servidor http timeout conexion red")
    c.consolidar_concepto("omega_nodo")
    indexar_nodo_sdm(c, "alpha_nodo")
    indexar_nodo_sdm(c, "omega_nodo")
    sims = similitudes_sdm_pool(c, "mamifero domestico felidae", ["alpha_nodo"])
    assert "alpha_nodo" in sims
    assert "omega_nodo" not in sims
    n = c.cursor.execute("SELECT COUNT(*) FROM nodos_sdm").fetchone()[0]
    assert n == 2
    c.cerrar_sistema()


def test_sin_vectores_degrada_vacio(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e2empty.db"))
    c.percibir_corto_plazo("solo_texto", "contenido sin vector persistido xyz")
    c.consolidar_concepto("solo_texto")
    c.cursor.execute("DELETE FROM nodos_sdm")
    c.conn.commit()
    assert similitudes_sdm_pool(c, "tres tokens aqui", ["solo_texto"]) == {}
    c.cerrar_sistema()


def test_peso_cap_y_off():
    assert 0.0 <= SDM_SCORING_PESO <= 0.08


def test_scoring_no_fusiona(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e2nf.db"))
    c.percibir_corto_plazo("n1", "uno dos tres cuatro")
    c.consolidar_concepto("n1")
    c.percibir_corto_plazo("n2", "cinco seis siete ocho")
    c.consolidar_concepto("n2")
    indexar_nodo_sdm(c, "n1")
    indexar_nodo_sdm(c, "n2")
    c.buscar_por_frase("uno dos tres cuatro", limite=5)
    n = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    c.cerrar_sistema()
    assert n == 2
