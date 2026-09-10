"""E9: IDF de dimensiones cacheado, O(1) por candidato."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG


def _nodo(c, conc, cont):
    c.percibir_corto_plazo(conc, cont)
    c.consolidar_concepto(conc)


def test_idf_rara_mayor_que_comun(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "DIM_IDF_ACTIVO", True)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e9.db"))
    ids = [r[0] for r in c.cursor.execute(
        "SELECT id FROM dimensiones_semanticas ORDER BY id LIMIT 2"
    ).fetchall()]
    rara, comun = ids[0], ids[1]
    _nodo(c, "n_rara", "contenido unico xyzabc tokenraro")
    c.cursor.execute(
        "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
        ("n_rara", rara),
    )
    for i in range(8):
        name = f"n_comun_{i}"
        _nodo(c, name, f"contenido comun {i} tokencomun")
        c.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
            (name, comun),
        )
    c.conn.commit()
    c._dim_idf_map = None
    mp = c._asegurar_idf_dimensiones()
    assert mp[rara] > mp[comun]
    c.cerrar_sistema()


def test_flag_off_no_multiplica(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "DIM_IDF_ACTIVO", False)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e9off.db"))
    assert c._peso_dim_con_idf(1, 1.0) == 1.0
    c.cerrar_sistema()


def test_cache_una_vez(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "DIM_IDF_ACTIVO", True)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e9c.db"))
    a = c._asegurar_idf_dimensiones()
    b = c._asegurar_idf_dimensiones()
    assert a is b
    c.cerrar_sistema()


def test_fuente_buscar():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_peso_dim_con_idf" in src
