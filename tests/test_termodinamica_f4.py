"""F4: termodinámica cognitiva F = E - T·S (Plan Maestro, INVENCIÓN 4).

E = tensión pares co-activos sin arista; S = Shannon de grados;
T = temperatura param. Tests deterministas con DB tmp.
"""
import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.dmn_engine import (
    TERMODINAMICA_DMN,
    calcular_energia_libre_corteza,
    rankear_pares_por_delta_f,
    sintetizar_sinapsis_dmn,
    podar_ltd_guiado,
)


def _nodo(c, concepto, contenido, peso=1.0):
    c.percibir_corto_plazo(concepto, contenido)
    c.consolidar_concepto(concepto)
    c.cursor.execute(
        "UPDATE largo_plazo SET peso_sinaptico = ? WHERE concepto = ?",
        (peso, concepto.lower()),
    )
    c.conn.commit()


def _dims(c, links):
    """links: {concepto_lower: n_dims}. Crea cadena FK completa."""
    c.cursor.execute("INSERT OR IGNORE INTO tipos_dimension (nombre) VALUES ('f4tipo')")
    tid = c.cursor.execute(
        "SELECT id FROM tipos_dimension WHERE nombre = 'f4tipo'"
    ).fetchone()[0]
    ids = []
    for i in range(max(links.values())):
        c.cursor.execute(
            "INSERT OR IGNORE INTO dimensiones_semanticas (name, tipo_id) VALUES (?, ?)",
            (f"f4d{i}", tid),
        )
        ids.append(
            c.cursor.execute(
                "SELECT id FROM dimensiones_semanticas WHERE name = ?", (f"f4d{i}",)
            ).fetchone()[0]
        )
    for concepto, n in links.items():
        for did in ids[:n]:
            c.cursor.execute(
                "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) "
                "VALUES (?, ?)",
                (concepto, did),
            )
    c.conn.commit()


def _limpiar_sinapsis(c):
    # consolidar_concepto auto-crea sinapsis Hebbianas (tokens compartidos).
    # Para escenarios controlados se parte de grafo vacío explícito.
    c.cursor.execute("DELETE FROM sinapsis")
    c.conn.commit()


def test_default_off():
    assert TERMODINAMICA_DMN is False


def test_f_determinista(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f4.db"))
    _nodo(c, "tA", "puente cuantico primero", peso=1.0)
    _nodo(c, "tB", "puente cuantico segundo", peso=0.8)
    _limpiar_sinapsis(c)
    f1 = calcular_energia_libre_corteza(c, temperatura=1.0)
    f2 = calcular_energia_libre_corteza(c, temperatura=1.0)
    assert f1 == f2
    assert set(f1) == {"F", "E", "S", "T", "n", "aristas", "aislados"}
    assert f1["n"] == 2 and f1["aristas"] == 0 and f1["aislados"] == 2
    # Sin aristas: E>0 (tensión puente/cuantico), S=1.0 (dispersión total).
    assert f1["E"] > 0.0
    assert f1["S"] == pytest.approx(1.0)
    assert f1["F"] == pytest.approx(f1["E"] - f1["S"])


def test_crear_arista_baja_f(tmp_path):
    # 4 nodos: con n=2 una arista es orden total (S 1→0) y F subiría.
    c = SQLiteMemoryBioRAG(str(tmp_path / "f4b.db"))
    _nodo(c, "tA", "puente cuantico primero", peso=1.0)
    _nodo(c, "tB", "puente cuantico segundo", peso=0.8)
    _nodo(c, "tC", "valle norte andino", peso=0.1)
    _nodo(c, "tD", "lago monte quieto", peso=0.1)
    _limpiar_sinapsis(c)
    antes = calcular_energia_libre_corteza(c)
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
        "VALUES ('ta', 'tb', 0.3, 'f4test', 0)"
    )
    c.conn.commit()
    despues = calcular_energia_libre_corteza(c)
    assert despues["F"] < antes["F"]  # tensión resuelta supera T×orden
    assert despues["E"] == pytest.approx(0.0)


def test_ranking_prefiere_mayor_tension(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f4c.db"))
    _nodo(c, "tA", "puente cuantico alfa", peso=1.0)
    _nodo(c, "tB", "puente cuantico beta", peso=1.0)
    _nodo(c, "tC", "rio valle gamma", peso=1.0)
    _limpiar_sinapsis(c)
    # tA-tB tenso (tokens); tA-tC sin afinidad → ΔF 0 vs negativo.
    rank = rankear_pares_por_delta_f(c, [("ta", "tc"), ("ta", "tb")], temperatura=1.0)
    assert rank[0][:2] == ("ta", "tb")
    assert rank[0][2] < 0.0
    assert rank[1][2] > 0.0  # arista sin tensión: impone orden, sube F
    assert rank[0][2] < rank[1][2]


def test_t_cero_solo_energia(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f4t.db"))
    _nodo(c, "tA", "puente cuantico alfa", peso=1.0)
    _nodo(c, "tB", "puente cuantico beta", peso=1.0)
    _nodo(c, "tC", "puente delta gamma", peso=0.2)
    _limpiar_sinapsis(c)
    # T=0 → ΔF = -tensión: tA-tB (1.0*1.0*1.0); tA-tC no es candidato → 0.0.
    rank = rankear_pares_por_delta_f(c, [("ta", "tc"), ("ta", "tb")], temperatura=0.0)
    assert rank[0][:2] == ("ta", "tb")
    assert rank[0][2] == pytest.approx(-1.0)
    assert rank[1][2] == pytest.approx(0.0)


def test_off_vs_on_sintesis(tmp_path, monkeypatch):
    import core.dmn_engine as dm
    # A-B: 3 dims, peso bajo → n alto, tensión baja. A-C: 1 dim, peso alto.
    # OFF (E10): elige A-B (ORDER BY n DESC). ON (F4): elige A-C (ΔF menor).
    for flag, esperado in ((False, ("nda", "ndb")), (True, ("nda", "ndc"))):
        monkeypatch.setattr(dm, "TERMODINAMICA_DMN", flag)
        c = SQLiteMemoryBioRAG(str(tmp_path / f"f4s{int(flag)}.db"))
        _nodo(c, "ndA", "zxq alfa uno", peso=1.0)
        _nodo(c, "ndB", "wvb beta dos", peso=0.1)
        _nodo(c, "ndC", "kjm gamma tres", peso=0.9)
        _dims(c, {"nda": 3, "ndb": 3, "ndc": 1})
        n = sintetizar_sinapsis_dmn(c, max_n=1)
        assert n == 1
        row = c.cursor.execute(
            "SELECT origen, destino FROM sinapsis WHERE tipo = 'dmn_synthesized'"
        ).fetchone()
        assert (row[0], row[1]) == esperado, f"flag={flag}"
        c.cerrar_sistema()


def test_ltd_protege_arista_estructural(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f4l.db"))
    _nodo(c, "tX", "puente cuantico equis", peso=1.0)
    _nodo(c, "tY", "puente cuantico ipsilon", peso=1.0)
    _nodo(c, "tP", "rio seco norte", peso=0.5)
    _nodo(c, "tQ", "valle verde sur", peso=0.5)
    _limpiar_sinapsis(c)
    # Débil pero estructural (tensa) vs débil y redundante.
    c.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES "
        "('tx', 'ty', 0.04, 'f4test', 0), ('tp', 'tq', 0.04, 'f4test', 0)"
    )
    c.conn.commit()
    n = podar_ltd_guiado(c, temperatura=1.0)
    assert n == 1
    queda = {r[0] for r in c.cursor.execute("SELECT origen FROM sinapsis")}
    assert queda == {"tx"}  # tx-ty protegida (ΔF_remover>0); tp-tq podada
