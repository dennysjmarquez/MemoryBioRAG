"""E5: resonancia multi-semilla solo sobre vecinos que ya estan en el pool."""
import time

from core.memory_store import SQLiteMemoryBioRAG, RESONANCIA_PESO


def _nodo(c, conc, cont):
    c.percibir_corto_plazo(conc, cont)
    c.consolidar_concepto(conc)


def test_convergencia_dos_semillas_supera_una(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_RESONANCIA_ACTIVA", "1")
    db = tmp_path / "e5.db"
    c = SQLiteMemoryBioRAG(str(db))
    _nodo(c, "sem_a", "tokenalfa ancla una")
    _nodo(c, "sem_b", "tokenbeta ancla dos")
    _nodo(c, "hub_comun", "nodo puente sin overlap de query")
    _nodo(c, "solo_a", "vecino exclusivo de a")
    now = time.time()
    for o, d, w in (
        ("sem_a", "hub_comun", 0.9),
        ("sem_b", "hub_comun", 0.9),
        ("sem_a", "solo_a", 0.9),
    ):
        c.cursor.execute(
            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?,?,?,?,?)",
            (o, d, w, "manual", now),
        )
    c.conn.commit()
    scores = c._resonancia_multi_semilla(
        ["sem_a", "sem_b"], ["sem_a", "sem_b", "hub_comun", "solo_a"]
    )
    assert scores.get("hub_comun", 0) > scores.get("solo_a", 0)
    assert "fuera_del_pool" not in scores
    c.cerrar_sistema()


def test_fuera_del_pool_no_cuenta(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e5p.db"))
    _nodo(c, "s1", "aaa bbb ccc ddd")
    _nodo(c, "oculto", "no esta en el pool de scoring")
    now = time.time()
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?,?,?,?,?)",
        ("s1", "oculto", 0.95, "manual", now),
    )
    c.conn.commit()
    scores = c._resonancia_multi_semilla(["s1"], ["s1"])
    assert "oculto" not in scores
    n = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    assert n == 2
    c.cerrar_sistema()


def test_formula_suma_resonancia(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "e5f.db"))
    s0 = c._calcular_score_hibrido(bm25_norm=0.5, resonancia_score=0.0)
    s1 = c._calcular_score_hibrido(bm25_norm=0.5, resonancia_score=1.0)
    c.cerrar_sistema()
    if RESONANCIA_PESO > 0:
        assert s1 > s0
    else:
        assert s1 == s0


def test_fuente_buscar():
    import inspect
    from core.memory_store import SQLiteMemoryBioRAG
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_resonancia_multi_semilla" in src
    assert "resonancia_score" in src
