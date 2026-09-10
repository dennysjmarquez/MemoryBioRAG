"""E4: spreading proactivo inyecta 1-hop aunque el pool léxico ya sea grande."""
import os
import time

from core.memory_store import SQLiteMemoryBioRAG


def _nodo(c, conc, cont):
    c.percibir_corto_plazo(conc, cont)
    c.consolidar_concepto(conc)


def test_inyecta_vecino_fuera_de_fts(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_SPREADING_PROACTIVO", "1")
    monkeypatch.setenv("BIORAG_QCR_ACTIVO", "0")
    db = tmp_path / "e4.db"
    c = SQLiteMemoryBioRAG(str(db))
    _nodo(c, "semilla_fts_alpha", "tokenunicoalpha contenido de ancla lexical")
    for i in range(4):
        _nodo(c, f"ruido_alpha_{i}", f"tokenunicoalpha distractor {i}")
    _nodo(c, "vecino_sin_overlap", "zzz yyy xxx sin palabras compartidas con la query")
    now = time.time()
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?,?,?,?,?)",
        ("semilla_fts_alpha", "vecino_sin_overlap", 0.85, "manual", now),
    )
    c.conn.commit()
    res, _ = c.buscar_por_frase("tokenunicoalpha", limite=10)
    nombres = [r[0] for r in res]
    assert "semilla_fts_alpha" in nombres
    assert "vecino_sin_overlap" in nombres
    assert c.last_origen_scores.get("vecino_sin_overlap", ("", 0))[0] == "spreading_proactivo"
    c.cerrar_sistema()


def test_flag_off_no_inyecta(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_SPREADING_PROACTIVO", "0")
    monkeypatch.setenv("BIORAG_QCR_ACTIVO", "0")
    db = tmp_path / "e4off.db"
    c = SQLiteMemoryBioRAG(str(db))
    _nodo(c, "semilla_fts_beta", "tokenunicobeta ancla")
    for i in range(4):
        _nodo(c, f"ruido_beta_{i}", f"tokenunicobeta distractor {i}")
    _nodo(c, "vecino_oculto", "nodo aislado de vocabulario")
    now = time.time()
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?,?,?,?,?)",
        ("semilla_fts_beta", "vecino_oculto", 0.9, "manual", now),
    )
    c.conn.commit()
    res, _ = c.buscar_por_frase("tokenunicobeta", limite=10)
    orig = c.last_origen_scores.get("vecino_oculto", ("", 0))[0]
    assert orig != "spreading_proactivo"
    c.cerrar_sistema()


def test_fuente_existe():
    import inspect
    from core.memory_store import SQLiteMemoryBioRAG
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_spreading_proactivo" in src
    assert "spreading_proactivo" in src
