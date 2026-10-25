"""Pruebas de la neurona asociativa (experimento 11).

No necesitan internet, NLTK ni ninguna DB: usan memorias inventadas chiquitas.
Correr:  python -m pytest -q test_neurona_asociativa.py
"""
import json
import os
import sys
import time

import numpy as np
import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import agujas  # noqa: E402
import neurona_asociativa as na  # noqa: E402

TEMAS = {
    "cocina": "receta horno harina azucar mantequilla hornear pastel masa levadura",
    "futbol": "partido gol arbitro estadio jugador equipo liga campeonato balon",
    "astronomia": "telescopio estrella galaxia planeta orbita cometa nebulosa luna",
    "medicina": "paciente doctor sintoma diagnostico tratamiento hospital vacuna",
    "musica": "guitarra melodia acorde concierto partitura ritmo cancion piano",
}


def memoria_de_prueba(n_por_tema=8, semilla=0, con_tiempo=False, con_etiquetas=False):
    rng = np.random.default_rng(semilla)
    textos, tema, orden, etq = [], [], [], []
    relleno = "dia cosa gente tiempo forma parte lugar caso vez mundo".split()
    k = 0
    for t, palabras in TEMAS.items():
        p = palabras.split()
        for _ in range(n_por_tema):
            w = list(rng.choice(p, 6)) + list(rng.choice(relleno, 4))
            textos.append(" ".join(w))
            tema.append(t)
            orden.append(float(k))
            etq.append(frozenset([t[:3]]))
            k += 1
    return textos, tema, (orden if con_tiempo else None), (etq if con_etiquetas else None)


@pytest.fixture(scope="module")
def mem():
    textos, tema, orden, etq = memoria_de_prueba(con_tiempo=True, con_etiquetas=True)
    return agujas.Memoria(textos, orden=orden, etiquetas=etq), tema


# ---------------- agujas ----------------

def test_forma_rango_y_sin_nan(mem):
    m, _ = mem
    pares = m.candidatos()
    F = m.agujas(pares)
    assert F.shape == (len(pares), len(agujas.NOMBRES_TODAS))
    assert np.all(np.isfinite(F))
    assert F.min() >= 0.0 and F.max() <= 1.0


def test_nombres_iguales_en_agujas_y_neurona():
    assert agujas.NOMBRES == na.AGUJAS
    assert agujas.CONTEXTO == na.CONTEXTO and agujas.NOMBRES_TODAS == na.ENTRADAS
    assert "corto" not in agujas.NOMBRES          # se probó en la v1 y se sacó (README §2)


def test_simetria_a_b(mem):
    m, _ = mem
    pares = m.candidatos()[:200]
    F1 = m.agujas(pares)
    F2 = m.agujas([(b, a) for a, b in pares])
    assert np.allclose(F1, F2, atol=1e-6)


def test_determinismo():
    textos, _, orden, etq = memoria_de_prueba(con_tiempo=True, con_etiquetas=True)
    m1 = agujas.Memoria(textos, orden=orden, etiquetas=etq)
    m2 = agujas.Memoria(textos, orden=orden, etiquetas=etq)
    p1, p2 = m1.candidatos(), m2.candidatos()
    assert p1 == p2
    assert np.array_equal(m1.agujas(p1), m2.agujas(p2))
    assert np.array_equal(na.fuerza(m1.agujas(p1), agujas.NOMBRES_TODAS, p=None),
                          na.fuerza(m2.agujas(p2), agujas.NOMBRES_TODAS, p=None))


def test_mismo_tema_mas_fuerte_que_distinto(mem):
    m, tema = mem
    pares = m.candidatos()
    f = na.fuerza(m.agujas(pares), agujas.NOMBRES_TODAS, p=None)
    y = np.array([tema[a] == tema[b] for a, b in pares]).astype(int)
    assert na._auc(f, y) > 0.9


@pytest.mark.parametrize("textos", [[], ["uno solo"], ["dos textos", "muy distintos"],
                                    ["hola mundo"] * 3])
def test_memorias_minimas_no_rompen(textos):
    m = agujas.Memoria(textos, orden=list(range(len(textos))) or None, etiquetas=[{"x"}] * len(textos) or None)
    pares = m.candidatos()
    F = m.agujas(pares)
    assert F.shape == (len(pares), len(agujas.NOMBRES_TODAS))
    assert np.all(np.isfinite(F))
    f = na.fuerza(F, agujas.NOMBRES_TODAS, p=None)
    assert np.all(np.isfinite(f))


def test_textos_todos_iguales_no_inventan_relacion():
    """Si todos los recuerdos son iguales, ninguna palabra distingue: el vocabulario útil queda
    vacío y las agujas de texto valen 0 (no se inventan diferencias por empates)."""
    m = agujas.Memoria(["el mismo texto repetido otra vez"] * 20)
    pares = [(0, 1), (2, 3), (5, 19)]
    F = m.agujas(pares)
    assert np.allclose(F, F[0])                     # todos los pares valen lo mismo
    i = agujas.NOMBRES.index
    assert F[0, i("parecido")] == 0 and F[0, i("mutuo")] == 0 and F[0, i("vecinos")] == 0


def test_textos_sin_vocabulario_comun():
    textos = [f"palabra{i}a cosa{i}b objeto{i}c" for i in range(30)]
    m = agujas.Memoria(textos)
    pares = [(0, 1), (3, 7), (10, 29)]
    F = m.agujas(pares)
    i = agujas.NOMBRES.index
    for a in ("parecido", "rareza_max", "cobertura", "mutuo", "vecinos"):
        assert np.all(F[:, i(a)] == 0), a


def test_tiempo_sin_relacion_con_texto_se_apaga():
    """Si en esta memoria el orden de llegada es puro azar respecto al texto, la aguja episodio
    se apaga sola (fiabilidad ~0): la neurona no confía a ciegas en el reloj."""
    textos, tema, _, _ = memoria_de_prueba(n_por_tema=20)
    rng = np.random.default_rng(1)
    orden_azar = list(rng.permutation(len(textos)).astype(float))
    m = agujas.Memoria(textos, orden=orden_azar)
    assert m.fiab_episodio < 0.15
    textos_ord = sorted(range(len(textos)), key=lambda k: tema[k])
    orden_tema = [float(textos_ord.index(k)) for k in range(len(textos))]
    m2 = agujas.Memoria(textos, orden=orden_tema)
    assert m2.fiab_episodio > 0.5


def test_sin_tiempo_ni_etiquetas_valen_cero():
    textos, _, _, _ = memoria_de_prueba()
    m = agujas.Memoria(textos)
    F = m.agujas(m.candidatos())
    assert np.all(F[:, agujas.NOMBRES.index("episodio")] == 0)
    assert np.all(F[:, agujas.NOMBRES.index("etiquetas")] == 0)


def test_candidatos_tienen_vecinos_de_tiempo():
    textos, _, orden, _ = memoria_de_prueba(con_tiempo=True)
    m = agujas.Memoria(textos, orden=orden)
    pares = set(m.candidatos())
    for k in range(len(textos) - 1):
        assert (k, k + 1) in pares


# ---------------- neurona ----------------

def test_fuerza_en_0_1_y_extremos_no_desbordan():
    F = np.zeros((3, len(agujas.NOMBRES_TODAS)))
    F[1] = 1.0
    F[2] = np.nan
    f = na.fuerza(F, agujas.NOMBRES_TODAS, p=None)
    assert np.all((f >= 0) & (f <= 1)) and np.all(np.isfinite(f))
    assert f[1] > f[0]


def test_monotonia_del_piso():
    """Subir una aguja que suma nunca baja la fuerza del piso; subir una que resta nunca la sube."""
    base = np.full((1, len(agujas.NOMBRES_TODAS)), 0.3)
    f0 = na.fuerza(base, agujas.NOMBRES_TODAS, p=None)[0]
    for k, a in enumerate(agujas.NOMBRES):
        F = base.copy()
        F[0, k] = 0.9
        f1 = na.fuerza(F, agujas.NOMBRES_TODAS, p=None)[0]
        w = na.PISO.get(a, 0.0)
        if w > 0:
            assert f1 > f0, a
        elif w < 0:
            assert f1 < f0, a
        else:
            assert abs(f1 - f0) < 1e-12, a


def test_correccion_respeta_el_techo():
    p = na.nuevos_pesos(0)
    p["v"] = np.full(na.OCULTAS, 100.0)
    X = np.random.default_rng(0).uniform(0, 1, (500, len(na.ENTRADAS)))
    c = na.correccion(p, X)
    assert np.all(np.abs(c) <= na.TECHO + 1e-9)


def test_competencia_k():
    rng = np.random.default_rng(0)
    pares = [(a, b) for a in range(30) for b in range(a + 1, 30) if rng.uniform() < 0.5]
    f = rng.uniform(0, 0.7, len(pares))              # nadie llega a "conectar"
    for k in (1, 5, 10):
        keep = na.competencia(f, pares, k)
        for nodo in range(30):
            mios = [i for i, (a, b) in enumerate(pares) if nodo in (a, b)]
            ganados = [i for i in mios if keep[i]]
            assert len(ganados) >= min(k, len(mios))          # nadie se queda solo
            top = sorted(mios, key=lambda i: -f[i])[:k]
            assert all(keep[i] for i in top)                  # sus k mejores siempre se quedan
    assert na.competencia(f, pares, 5).tolist() == na.competencia(f, pares, 5).tolist()


def test_competencia_umbral_conectar_siempre_entra():
    pares = [(0, i) for i in range(1, 30)]
    f = np.full(len(pares), 0.1)
    f[-1] = 0.95
    f[:10] = 0.5
    keep = na.competencia(f, pares, 3)
    assert keep[-1]


def test_guardar_y_cargar(tmp_path):
    p = na.nuevos_pesos(3)
    p["v"] = np.arange(na.OCULTAS, dtype=float) / 10
    p["escala"] = 0.5
    ruta = str(tmp_path / "pesos.json")
    na.guardar(p, ruta=ruta)
    q = na.cargar(ruta)
    assert q is not None
    for k in ("W", "b", "v"):
        assert np.allclose(p[k], q[k])
    assert q["escala"] == 0.5


@pytest.mark.parametrize("cambio", ["agujas", "version", "piso", "techo", "roto", "nan"])
def test_cargar_rechaza_pesos_de_otra_version(tmp_path, cambio):
    """Si cambian las agujas, el piso, el techo o el archivo está roto, NO se usan pesos viejos:
    la neurona vuelve al piso solo (cargar -> None)."""
    p = na.nuevos_pesos(0)
    ruta = str(tmp_path / "pesos.json")
    na.guardar(p, ruta=ruta)
    d = json.load(open(ruta))
    if cambio == "agujas":
        d["agujas"] = d["agujas"][:-1]
    elif cambio == "version":
        d["version"] = -1
    elif cambio == "piso":
        d["piso"] = dict(d["piso"], sesgo=99)
    elif cambio == "techo":
        d["techo"] = 50
    elif cambio == "nan":
        d["v"] = [float("nan")] * len(d["v"])
    if cambio == "roto":
        open(ruta, "w").write("{esto no es json")
    else:
        json.dump(d, open(ruta, "w"))
    assert na.cargar(ruta) is None


def test_pesos_de_fabrica_del_repo_cargan():
    p = na.cargar()
    assert p is not None, "pesos_fabrica.json no corresponde a esta versión de la neurona"
    assert 0.0 <= p["escala"] <= 1.0


def _pares_si_no(y, filas, rng, n=5000):
    si, no = filas[y[filas] == 1], filas[y[filas] == 0]
    return si[rng.integers(0, len(si), n)], no[rng.integers(0, len(no), n)]


def test_entrenar_nunca_queda_bajo_el_piso():
    """Con datos donde el piso ya ordena perfecto, la corrección no puede empeorarlo en ninguna guardia;
    si no logra mejorar sin empeorar, queda apagada (escala 0)."""
    rng = np.random.default_rng(0)
    Z = rng.uniform(0, 1, (3000, len(na.ENTRADAS)))
    y = (na.piso(Z) > np.median(na.piso(Z))).astype(int)
    estudio = [("a", Z, *_pares_si_no(y, np.arange(1000, 3000), rng))]
    G = [("a", Z, *_pares_si_no(y, np.arange(0, 500), rng)), ("b", Z, *_pares_si_no(y, np.arange(500, 1000), rng))]
    p, info = na.entrenar(estudio, G, pasos=300, paciencia=150)
    for nm, Zg, gs, gn in G:
        assert na.auc_por_recuerdo(na.piso(Zg) + na.correccion(p, Zg), gs, gn) >= \
            na.auc_por_recuerdo(na.piso(Zg), gs, gn) - 0.001
    assert info["escala"] in (0.0, 1.0)


def test_entrenar_aprende_cuando_hay_algo_que_aprender():
    """Si la verdad depende de una aguja que el piso no usa, la corrección la aprende."""
    rng = np.random.default_rng(1)
    Z = rng.uniform(0, 1, (4000, len(na.ENTRADAS)))
    j = na.ENTRADAS.index("cobertura")             # el piso le da peso 0
    z = na.piso(Z) + 6 * Z[:, j]
    y = (z > np.median(z)).astype(int)
    estudio = [("a", Z, *_pares_si_no(y, np.arange(1000, 4000), rng, 20000))]
    G = [("a", Z, *_pares_si_no(y, np.arange(0, 1000), rng))]
    p, info = na.entrenar(estudio, G, pasos=800, paciencia=300)
    assert info["escala"] == 1.0
    gs, gn = G[0][2], G[0][3]
    assert na.auc_por_recuerdo(na.piso(Z) + na.correccion(p, Z), gs, gn) > na.auc_por_recuerdo(na.piso(Z), gs, gn) + 0.01


def test_auc_por_recuerdo():
    z = np.array([3.0, 1.0, 2.0, 2.0])
    assert na.auc_por_recuerdo(z, np.array([0, 2]), np.array([1, 3])) == 0.75   # 1 gana, 1 empata
    assert na.auc_por_recuerdo(z, np.array([], dtype=int), np.array([], dtype=int)) == 0.5


def test_velocidad_decision_por_par():
    """Decidir un par (dadas sus agujas) es una fórmula de 12 números: tiempo constante."""
    p = na.cargar()
    F = np.random.default_rng(0).uniform(0, 1, (10000, len(agujas.NOMBRES_TODAS)))
    t = time.perf_counter()
    na.fuerza(F, agujas.NOMBRES_TODAS, p=p)
    assert (time.perf_counter() - t) / len(F) < 2e-5        # < 20 microsegundos por par
