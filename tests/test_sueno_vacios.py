"""Mision c: consolidacion de vacios epistemicos en el ciclo de sueno."""
import json

import pytest

from core.memory_store import SQLiteMemoryBioRAG
from core.sueno_vacios import (
    SUENO_PESO_LATENTE,
    SUENO_PESO_SINAPSIS,
    SUENO_TIPO,
    afinidad_candidatos,
    consolidar_vacios,
)


@pytest.fixture()
def cerebro_tmp(tmp_path):
    return SQLiteMemoryBioRAG(db_path=str(tmp_path / "sueno.db"))


@pytest.fixture()
def hormiga_tmp(tmp_path, monkeypatch):
    p = str(tmp_path / "hormiga.json")
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", p)
    return p


def _nodo(cz, concepto, contenido, peso=0.5):
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES (?, ?, ?, 'activo')",
        (concepto, contenido, peso),
    )


def _sembrar_trio(cz, con_dims=True):
    _nodo(cz, "nodo_alfa", "puente resonante alfa para prueba")
    _nodo(cz, "nodo_beta", "puente resonante beta para prueba")
    _nodo(cz, "nodo_gamma", "puente resonante gamma para prueba")
    if con_dims:
        for c in ("nodo_alfa", "nodo_beta", "nodo_gamma"):
            cz.cursor.execute(
                "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id)"
                " VALUES (?, 7)",
                (c,),
            )
    cz.conn.commit()


def _encolar(path, items):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"vacios_cognitivos": items}, f)


def test_cola_vacia_noop(cerebro_tmp, hormiga_tmp):
    """Sin cola/archivo: resumen en ceros, 0 filas, sin excepcion."""
    r = consolidar_vacios(cerebro_tmp)
    assert r["atendidos"] == 0 and r["sinapsis_nuevas"] == 0
    assert r["latentes_nuevas"] == 0
    assert cerebro_tmp.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0] == 0


def test_consolida_pares_y_drena(cerebro_tmp, hormiga_tmp):
    """3 candidatos -> 3 pares: tipo/peso exactos, cola drenada, log completo."""
    cz = cerebro_tmp
    _sembrar_trio(cz)
    _encolar(hormiga_tmp, [{"termino": "puente resonante desconocido", "Ce": 0.1, "ts": 1}])

    cands = afinidad_candidatos(cz, "puente resonante desconocido")
    assert len(cands) == 3  # los 3 por FTS

    r = consolidar_vacios(cz)
    assert r["atendidos"] == 1 and r["sin_pares"] == 0 and r["omitidos"] == 0
    assert r["sinapsis_nuevas"] == 3 and r["latentes_nuevas"] == 3

    rows = cz.cursor.execute(
        "SELECT peso, tipo FROM sinapsis WHERE tipo=?", (SUENO_TIPO,)
    ).fetchall()
    assert len(rows) == 3 and all(p == SUENO_PESO_SINAPSIS and t == SUENO_TIPO for p, t in rows)
    have = {r[1] for r in cz.cursor.execute("PRAGMA table_info(sinapsis_latentes)")}
    sel = "peso_atenuado, saltos, pmi_score, tiene_dim_comun" + (", strikes" if "strikes" in have else "")
    lats = cz.cursor.execute("SELECT %s FROM sinapsis_latentes" % sel).fetchall()
    assert len(lats) == 3
    assert all(
        p == SUENO_PESO_LATENTE and s == 2 and pm == 0.0 and d == 1
        for p, s, pm, d, *_ in lats
    )
    if "strikes" in have:
        assert all(r[-1] == 0 for r in lats)

    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_cognitivos"] == []
    proc = est["vacios_procesados"]
    assert len(proc) == 1 and len(proc[0]["candidatos"]) == 3
    assert proc[0]["termino"] == "puente resonante desconocido"
    assert len(proc[0]["pares"]) == 3


def test_idempotencia_segunda_vuelta_cero(cerebro_tmp, hormiga_tmp):
    """Re-ejecucion: 0 nuevas (cola vacia + dedup de pares)."""
    cz = cerebro_tmp
    _sembrar_trio(cz, con_dims=False)
    _encolar(hormiga_tmp, [{"termino": "puente resonante x", "Ce": 0.2, "ts": 1}])
    r1 = consolidar_vacios(cz)
    assert r1["sinapsis_nuevas"] == 3
    # Mismo vacio re-encolado (nueva consulta identica no resuelta)
    _encolar(hormiga_tmp, [{"termino": "puente resonante x", "Ce": 0.2, "ts": 2}])
    r2 = consolidar_vacios(cz)
    assert r2["atendidos"] == 1  # se atiende (log), pero...
    assert r2["sinapsis_nuevas"] == 0 and r2["latentes_nuevas"] == 0  # ...0 duplicados
    assert cz.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0] == 3


def test_dedup_respeta_conexion_existente_cualquier_tipo(cerebro_tmp, hormiga_tmp):
    """Par con arista previa (otro tipo) no recibe hipotesis redundante."""
    cz = cerebro_tmp
    _sembrar_trio(cz, con_dims=False)
    cz.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso)"
        " VALUES ('nodo_alfa', 'nodo_beta', 0.9, 'manual', 1, 1)"
    )
    _have = {r[1] for r in cz.cursor.execute("PRAGMA table_info(sinapsis_latentes)")}
    _cols = ["origen", "destino", "peso_atenuado", "saltos", "calculado_en",
             "pmi_score", "tiene_dim_comun"] + (["strikes"] if "strikes" in _have else [])
    _vals = ["nodo_beta", "nodo_gamma", 0.4, 2, 1, 0.0, 0] + ([0] if "strikes" in _have else [])
    cz.cursor.execute(
        "INSERT INTO sinapsis_latentes (%s) VALUES (%s)" % (",".join(_cols), ",".join("?" * len(_cols))),
        tuple(_vals),
    )
    cz.conn.commit()
    _encolar(hormiga_tmp, [{"termino": "puente resonante y", "Ce": 0.2, "ts": 1}])
    r = consolidar_vacios(cz)
    assert r["sinapsis_nuevas"] == 2  # 3 pares - 1 existente
    assert r["latentes_nuevas"] == 2  # 3 pares - 1 existente
    assert cz.cursor.execute(
        "SELECT COUNT(*) FROM sinapsis WHERE origen='nodo_alfa' AND destino='nodo_beta'"
    ).fetchone()[0] == 1  # la manual intacta, sin duplicado


def test_items_malos_no_abortan_ni_atascan(cerebro_tmp, hormiga_tmp):
    """Items corruptos se omiten con rastro; el bueno se procesa; cola drenada."""
    cz = cerebro_tmp
    _sembrar_trio(cz, con_dims=False)
    _encolar(
        hormiga_tmp,
        [
            {"termino": "puente resonante z", "Ce": 0.2, "ts": 1},
            {"termino": "   "},
            {"foo": 1},
            "cadena-suelta",
        ],
    )
    r = consolidar_vacios(cz)
    assert r["atendidos"] == 1 and r["omitidos"] == 3
    assert r["sinapsis_nuevas"] == 3
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_cognitivos"] == []  # venenos descartados, no reintentan
    assert len(est["vacios_procesados"]) == 1


def test_sin_pares_drena_igual(cerebro_tmp, hormiga_tmp):
    """Vacio sin candidatos (<2): 0 aristas pero se drena y se registra."""
    cz = cerebro_tmp
    _sembrar_trio(cz, con_dims=False)
    _encolar(hormiga_tmp, [{"termino": "zzzqqq inexistente kkk", "Ce": 0.05, "ts": 1}])
    r = consolidar_vacios(cz)
    assert r["atendidos"] == 1 and r["sin_pares"] == 1
    assert r["sinapsis_nuevas"] == 0 and r["latentes_nuevas"] == 0
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_cognitivos"] == []
    assert est["vacios_procesados"][0]["candidatos"] == []
