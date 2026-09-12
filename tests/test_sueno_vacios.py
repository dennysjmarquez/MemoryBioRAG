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
# ---------------- v2: fallback semantico PPMI ----------------
import numpy as np


def _idx_fake(termino, nombres, cosenos):
    """IndicesBioRAG con vectores inyectados (patron F3 aprobado).

    `cosenos`: dict nombre -> coseno deseado aprox (1.0/0.0/-1.0).
    """
    from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar
    toks = [t for t in _tokenizar(termino or "")]
    assert toks, "tokenizer vacio para %r" % termino
    base = np.array([1.0, 0.0, 0.0, 0.0])
    orto = np.array([0.0, 1.0, 0.0, 0.0])
    token_vecs = {t: base.copy() for t in toks}
    vecs = {}
    for n in nombres:
        c = cosenos.get(n, 1.0)
        vecs[n] = base.copy() if c >= 0.9 else (orto.copy() if c >= -0.1 else -base.copy())
    idx = IndicesBioRAG.__new__(IndicesBioRAG)
    idx.token_vecs = token_vecs
    idx.token_freq = {t: 1 for t in toks}
    idx.vecs = vecs
    idx.todos_los_conceptos = list(nombres)
    idx.n_docs = max(len(nombres), 1)
    return idx


def test_fallback_semantico_rescata_sin_pares(cerebro_tmp, hormiga_tmp):
    """0 hits FTS + vecinos PPMI -> 3 pares via semantica, cola drenada."""
    from core.sueno_vacios import consolidar_vacios
    cz = cerebro_tmp
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('sem_a', 'manzana pera fruta', 0.5, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('sem_b', 'naranja uva citrico', 0.5, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('sem_c', 'sandia melon dulce', 0.5, 'activo')"
    )
    cz.conn.commit()
    termino = "zzzqqq kkkvvv"
    _encolar(hormiga_tmp, [{"termino": termino, "Ce": 0.1, "ts": 1}])
    idx = _idx_fake(termino, ["sem_a", "sem_b", "sem_c"], {})
    r = consolidar_vacios(cz, idx_sem=idx)
    assert r["atendidos"] == 1 and r["sin_pares"] == 0
    assert r["sinapsis_nuevas"] == 3 and r["latentes_nuevas"] == 3
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_cognitivos"] == []
    assert est["vacios_procesados"][0]["via"] == "semantica"


def test_umbral_rechaza_lejanos(cerebro_tmp, hormiga_tmp):
    """Vecinos ortogonales/opuestos bajo umbral -> sin_pares, 0 aristas."""
    from core.sueno_vacios import consolidar_vacios
    cz = cerebro_tmp
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('lej_a', 'tornillo tuerca metal', 0.5, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('lej_b', 'martillo clavo golpe', 0.5, 'activo')"
    )
    cz.conn.commit()
    termino = "zzzqqq kkkvvv"
    _encolar(hormiga_tmp, [{"termino": termino, "Ce": 0.1, "ts": 1}])
    idx = _idx_fake(termino, ["lej_a", "lej_b"], {"lej_a": 0.0, "lej_b": -1.0})
    r = consolidar_vacios(cz, idx_sem=idx)
    assert r["atendidos"] == 1 and r["sin_pares"] == 1
    assert r["sinapsis_nuevas"] == 0 and r["latentes_nuevas"] == 0
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_cognitivos"] == []


def test_mixta_complementa_fts(cerebro_tmp, hormiga_tmp):
    """1 hit FTS + relleno PPMI -> via mixta con fuentes trazadas."""
    from core.sueno_vacios import consolidar_vacios
    cz = cerebro_tmp
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('mix_fts', 'contiene zzzqqq literal', 0.5, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('mix_s1', 'nada relacionado aqui', 0.5, 'activo')"
    )
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES ('mix_s2', 'otro texto distinto', 0.5, 'activo')"
    )
    cz.conn.commit()
    termino = "zzzqqq kkkvvv"
    _encolar(hormiga_tmp, [{"termino": termino, "Ce": 0.1, "ts": 1}])
    idx = _idx_fake(termino, ["mix_fts", "mix_s1", "mix_s2"], {})
    r = consolidar_vacios(cz, idx_sem=idx)
    assert r["atendidos"] == 1 and r["sin_pares"] == 0
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    proc = est["vacios_procesados"][0]
    assert proc["via"] == "mixta"
    assert proc["candidatos"][0] == "mix_fts"  # FTS primero, PPMI rellena


def test_v1_intacto_fallback_solo_si_falta(monkeypatch, cerebro_tmp, hormiga_tmp):
    """FTS>=2 -> fallback jamas invocado; FTS<2 -> exactamente 1 llamada."""
    import core.sueno_vacios as sv
    llamadas = []

    def _spy(cerebro, termino, k, umbral, idx=None, activos=None):
        llamadas.append(termino)
        return []

    monkeypatch.setattr(sv, "afinidad_semantica", _spy)
    cz = cerebro_tmp
    _sembrar_trio(cz, con_dims=False)
    _encolar(hormiga_tmp, [{"termino": "puente resonante w", "Ce": 0.2, "ts": 1}])
    r = sv.consolidar_vacios(cz)
    assert r["sinapsis_nuevas"] == 3 and llamadas == []
    est = json.load(open(hormiga_tmp, encoding="utf-8"))
    assert est["vacios_procesados"][0]["via"] == "lexica"
    _encolar(hormiga_tmp, [{"termino": "zzzqqq inexistente kkk", "Ce": 0.05, "ts": 2}])
    # idx inyectado: evita el build real (tmp DB no tiene tabla tokens PPMI)
    sv.consolidar_vacios(cz, idx_sem=_idx_fake("zzzqqq inexistente kkk", [], {}))
    assert llamadas == ["zzzqqq inexistente kkk"]
