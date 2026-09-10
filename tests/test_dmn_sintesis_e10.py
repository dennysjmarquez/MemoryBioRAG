"""E10: sinapsis dmn_synthesized con tope y evidencia tematica."""
from core.dmn_engine import sintetizar_sinapsis_dmn
from core.memory_store import SQLiteMemoryBioRAG


def test_flag_off_cero(tmp_path, monkeypatch):
    import core.dmn_engine as de
    monkeypatch.setattr(de, "DMN_SINTESIS_ACTIVA", False)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e10off.db"))
    assert sintetizar_sinapsis_dmn(c, max_n=8) == 0
    c.cerrar_sistema()


def test_crea_arista_con_dim_comun(tmp_path, monkeypatch):
    import core.dmn_engine as de
    import core.memory_store as ms
    monkeypatch.setattr(de, "DMN_SINTESIS_ACTIVA", True)
    monkeypatch.setattr(ms, "DMN_SINTESIS_ACTIVA", False)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e10dim.db"))
    dim_id = c.cursor.execute(
        "SELECT id FROM dimensiones_semanticas ORDER BY id LIMIT 1"
    ).fetchone()[0]
    for name, txt in (("alfa_e10", "contenido alfa tokenunicoaaa"),
                      ("beta_e10", "contenido beta tokenunicobbb")):
        c.percibir_corto_plazo(name, txt)
        c.consolidar_concepto(name)
        c.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
            (name, dim_id),
        )
    c.cursor.execute("DELETE FROM sinapsis WHERE origen IN ('alfa_e10','beta_e10') OR destino IN ('alfa_e10','beta_e10')")
    c.conn.commit()
    n = sintetizar_sinapsis_dmn(c, max_n=8)
    assert n >= 1
    row = c.cursor.execute(
        "SELECT tipo, peso FROM sinapsis WHERE "
        "(origen='alfa_e10' AND destino='beta_e10') OR (origen='beta_e10' AND destino='alfa_e10')"
    ).fetchone()
    assert row is not None
    assert row[0] == "dmn_synthesized"
    assert abs(row[1] - 0.30) < 1e-6
    n1 = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    sintetizar_sinapsis_dmn(c, max_n=8)
    n2 = c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    assert n1 == n2
    c.cerrar_sistema()


def test_tope_max(tmp_path, monkeypatch):
    import core.dmn_engine as de
    import core.memory_store as ms
    monkeypatch.setattr(de, "DMN_SINTESIS_ACTIVA", True)
    monkeypatch.setattr(ms, "DMN_SINTESIS_ACTIVA", False)
    c = SQLiteMemoryBioRAG(str(tmp_path / "e10max.db"))
    dim_id = c.cursor.execute(
        "SELECT id FROM dimensiones_semanticas ORDER BY id LIMIT 1"
    ).fetchone()[0]
    for i in range(6):
        name = f"nodo_e10_{i}"
        c.percibir_corto_plazo(name, f"texto independiente {i} xyz{i}abc")
        c.consolidar_concepto(name)
        c.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
            (name, dim_id),
        )
    c.cursor.execute("DELETE FROM sinapsis")
    c.conn.commit()
    n = sintetizar_sinapsis_dmn(c, max_n=2)
    assert n <= 2
    tot = c.cursor.execute(
        "SELECT COUNT(*) FROM sinapsis WHERE tipo='dmn_synthesized'"
    ).fetchone()[0]
    assert tot <= 2
    c.cerrar_sistema()
