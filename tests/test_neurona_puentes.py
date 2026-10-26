"""Contrato de la Neurona de Puentes.

Estos tests no comprueban que la neurona sea buena: comprueban que sea SEGURA.
Que se pueda meter dentro del hub sin poder romperlo. Si alguno falla, la
neurona no entra en el motor, por muy bien que prediga.
"""
import math
import random
import sqlite3

import numpy as np
import pytest

from core.memory import neurona_puentes as npu


# ───────────────────────── contrato de entrada ─────────────────────────

def test_rasgos_tiene_quince_entradas_y_todas_en_rango():
    r = npu.rasgos_puente(cobertura=0.83, idf_medio=0.6, idf_total=0.4,
                          n_query=4, n_puente=5, n_matched=3, fuera_vocab=0.25,
                          angulo="problema", margen=0.61, peso=1.0)
    assert len(r) == npu.N_ENTRADAS == 15
    assert all(0.0 <= v <= 1.0 for v in r), r


def test_rasgos_tolera_entradas_absurdas_sin_lanzar():
    r = npu.rasgos_puente(cobertura=None, idf_medio=float("nan"), idf_total=float("inf"),
                          n_query=0, n_puente=None, n_matched=99, fuera_vocab=-3,
                          angulo="inventado", margen=float("nan"), peso=None)
    assert len(r) == 15
    assert all(0.0 <= v <= 1.0 and math.isfinite(v) for v in r), r


def test_angulo_es_one_hot_exacto():
    for i, ang in enumerate(npu.ANGULOS):
        r = npu.rasgos_puente(0, 0, 0, 1, 1, 0, 0, ang, 0, 1)
        # las 5 posiciones del ángulo van de la 9 a la 13 (índices 8..12)
        assert r[8:13] == tuple(1.0 if j == i else 0.0 for j in range(5))


# ───────────────────────── contrato de salida ─────────────────────────

def test_neurona_recien_nacida_es_exactamente_neutra():
    """Sin entrenar, la salida tiene que ser 1.0. Indistinguible de no tenerla."""
    conn = sqlite3.connect(":memory:")
    for _ in range(50):
        x = tuple(random.random() for _ in range(npu.N_ENTRADAS))
        assert npu.multiplicador(conn, x) == 1.0


def test_salida_siempre_dentro_de_suelo_y_techo():
    """Fuzz: con pesos aleatorios grandes, nunca sale del rango prometido."""
    conn = sqlite3.connect(":memory:")
    rng = np.random.default_rng(7)
    for _ in range(20):
        p = dict(W=rng.normal(0, 5, (npu.N_OCULTAS, npu.N_ENTRADAS)),
                 b=rng.normal(0, 5, npu.N_OCULTAS),
                 v=rng.normal(0, 5, npu.N_OCULTAS))
        assert npu.guardar(conn, p)
        for _ in range(20):
            x = tuple(rng.random(npu.N_ENTRADAS))
            m = npu.multiplicador(conn, x)
            assert 0.5 <= m <= 1.0, (m, x)


def test_nunca_lanza_con_basura():
    """El contrato dice: cualquier fallo -> 1.0, nunca excepción."""
    conn = sqlite3.connect(":memory:")
    assert npu.multiplicador(conn, ()) == 1.0
    assert npu.multiplicador(conn, None) == 1.0
    assert npu.multiplicador(conn, ("a",) * 15) == 1.0
    assert npu.multiplicador(conn, (float("nan"),) * 15) == 1.0
    assert npu.multiplicador(conn, (1.0,) * 3) == 1.0
    assert npu.multiplicador(None, (0.5,) * 15) == 1.0  # conexión inválida


def test_solo_puede_atenuar_nunca_subir():
    """El techo es 1.0 por diseño: no puede inventar confianza.

    Con `v` de cualquier signo la corrección cambia de dirección, pero la
    salida nunca puede pasar de 1.0: el `min` con el techo lo impide por
    construcción, no por suerte.
    """
    conn = sqlite3.connect(":memory:")
    rng = np.random.default_rng(3)
    for _ in range(10):
        p = dict(W=rng.normal(0, 3, (npu.N_OCULTAS, npu.N_ENTRADAS)),
                 b=rng.normal(0, 3, npu.N_OCULTAS),
                 v=rng.normal(0, 3, npu.N_OCULTAS))
        npu.guardar(conn, p)
        for _ in range(20):
            assert npu.multiplicador(conn, tuple(rng.random(npu.N_ENTRADAS))) <= 1.0


def test_sin_correccion_devuelve_exactamente_uno():
    """Con la corrección en cero, la salida es 1.0 exacto (no 0.9999).

    Es la propiedad del molde: `c(x)=0` deja el motor igual que la fórmula a
    mano. Aquí `v=0` garantiza que la corrección sea cero para todo x.
    """
    conn = sqlite3.connect(":memory:")
    p = npu._nuevo_params()
    p["W"] = np.full((npu.N_OCULTAS, npu.N_ENTRADAS), 99.0)  # W grande, da igual
    npu.guardar(conn, p)
    for _ in range(20):
        assert npu.multiplicador(conn, tuple(random.random() for _ in range(15))) == 1.0


def test_es_determinista():
    conn = sqlite3.connect(":memory:")
    rng = np.random.default_rng(11)
    p = dict(W=rng.normal(0, 2, (npu.N_OCULTAS, npu.N_ENTRADAS)),
             b=rng.normal(0, 2, npu.N_OCULTAS),
             v=rng.normal(0, 2, npu.N_OCULTAS))
    npu.guardar(conn, p)
    x = tuple(rng.random(npu.N_ENTRADAS))
    assert npu.multiplicador(conn, x) == npu.multiplicador(conn, x)


# ───────────────────────── persistencia ─────────────────────────

def test_guardar_y_cargar_ida_y_vuelta():
    conn = sqlite3.connect(":memory:")
    rng = np.random.default_rng(5)
    p = dict(W=rng.normal(0, 1, (npu.N_OCULTAS, npu.N_ENTRADAS)),
             b=rng.normal(0, 1, npu.N_OCULTAS),
             v=rng.normal(0, 1, npu.N_OCULTAS))
    assert npu.guardar(conn, p)
    q = npu.cargar(conn)
    assert np.allclose(p["W"], q["W"]) and np.allclose(p["v"], q["v"])


def test_estado_corrupto_o_de_otra_version_vuelve_a_neutro():
    conn = sqlite3.connect(":memory:")
    npu._tabla(conn)
    conn.execute(f"INSERT INTO {npu._TABLA} VALUES ('pesos', ?, 0)",
                 ('{"version": 99, "n": 15, "W": [[1.0]]}',))
    conn.commit()
    assert npu.estado(conn)["neutra"] is True

    conn2 = sqlite3.connect(":memory:")
    npu._tabla(conn2)
    conn2.execute(f"INSERT INTO {npu._TABLA} VALUES ('pesos', ?, 0)", ("no es json",))
    conn2.commit()
    assert npu.multiplicador(conn2, (0.5,) * 15) == 1.0


def test_no_guarda_pesos_insanos():
    conn = sqlite3.connect(":memory:")
    p = npu._nuevo_params()
    p["W"][0, 0] = float("nan")
    assert npu.guardar(conn, p) is False
    p2 = npu._nuevo_params()
    p2["v"][0] = 1e9
    assert npu.guardar(conn, p2) is False


def test_estado_reporta_neutra_al_nacer():
    conn = sqlite3.connect(":memory:")
    e = npu.estado(conn)
    assert e["neutra"] is True and e["pesos_no_cero"] == 0
    assert e["entradas"] == 15 and e["ocultas"] == 4


# ───────────────────────── aprendizaje ─────────────────────────

def test_aprende_a_separar_ruido_de_acierto():
    """Caso sintético separable: tras entrenar, el ruido se atenúa y el acierto no."""
    rng = np.random.default_rng(1)
    # clase 0 (ruido): cobertura baja, nada compartido en la consulta
    ruido = np.column_stack([rng.uniform(0.20, 0.30, 60), rng.uniform(0, .2, 60),
                             rng.uniform(0, .2, 60), rng.uniform(0, .3, 60),
                             rng.uniform(0, .3, 60), rng.uniform(.5, 1, 60),
                             rng.uniform(0, .4, 60), rng.uniform(.7, 1, 60),
                             np.zeros((60, 5)), rng.uniform(0, .1, 60),
                             np.ones(60)])
    # clase 1 (acierto): cobertura alta, mucha coincidencia
    acierto = np.column_stack([rng.uniform(0.80, 1.0, 60), rng.uniform(.6, 1, 60),
                               rng.uniform(.6, 1, 60), rng.uniform(.7, 1, 60),
                               rng.uniform(.7, 1, 60), rng.uniform(0, .4, 60),
                               rng.uniform(0, .4, 60), rng.uniform(0, .1, 60),
                               np.zeros((60, 5)), rng.uniform(.6, 1, 60),
                               np.ones(60)])
    X = np.vstack([ruido, acierto])
    y = np.r_[np.zeros(60), np.ones(60)]

    p, info = npu.entrenar(X, y, pasos=120, lr=0.05)
    assert info["n"] == 120

    conn = sqlite3.connect(":memory:")
    assert npu.guardar(conn, p)
    m_ruido = np.mean([npu.multiplicador(conn, tuple(x)) for x in ruido])
    m_acierto = np.mean([npu.multiplicador(conn, tuple(x)) for x in acierto])
    assert m_ruido < m_acierto, (m_ruido, m_acierto)
    assert m_ruido < 0.95, m_ruido        # el ruido se atenúa de verdad
    assert m_acierto > 0.85, m_acierto    # el acierto se respeta


def test_entrenar_con_datos_vacios_no_rompe():
    p, info = npu.entrenar(np.zeros((0, 15)), np.zeros(0))
    assert info["n"] == 0 and npu._sano(p)
    assert np.all(p["v"] == 0.0)  # sigue neutra


def test_entrenar_no_acepta_formas_incorrectas():
    p, info = npu.entrenar(np.zeros((5, 3)), np.zeros(5))
    assert info["n"] == 0 and npu._sano(p)
