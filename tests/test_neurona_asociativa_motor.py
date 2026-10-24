"""v35 — Neurona asociativa en el motor: decide el PESO de nacimiento de las sinapsis.

Garantías que se prueban:
  1. Fiel al experimento 11: la fuerza del motor = la del experimento (mismas agujas, mismo piso).
  2. No crea ni corta sinapsis: con la neurona encendida o apagada nacen EXACTAMENTE las mismas.
  3. Peso siempre entre 0.5 y 1.0, y en el mismo orden que la fuerza.
  4. Apagada (BIORAG_NEURONA_ASOCIATIVA=0) = peso a mano de siempre, idéntico.
  5. Si falla, se aparta: el guardado sigue y usa el peso a mano.
  6. Nunca baja una sinapsis que ya existía (ON CONFLICT ... MAX).
  7. Memoria vacía o mínima: peso a mano (no inventa nada).
  8. El estado se rehace solo cuando la memoria crece; tiene techo de costo.
  9. Guardia de tiempo: recuerdos separados por más de 7 días reales no "se vivieron juntos".
"""
import importlib.util
import math
import os
import time

import numpy as np
import pytest

from core import neurona_asociativa as na
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos

EXP11 = os.path.join(os.path.dirname(__file__), "..", "docs", "Mi neurona en el sistema",
                     "experimento_11_neurona_asociativa")

TEMAS = {
    "cocina": ["receta de pan casero con harina levadura y horno caliente",
               "la masa de pan necesita levadura agua harina y reposo",
               "horno precalentado para hornear pan y galletas de harina",
               "galletas de mantequilla harina azucar y horno",
               "pizza casera masa levadura tomate queso horno"],
    "astronomia": ["telescopio para observar planetas estrellas y galaxias lejanas",
                   "la galaxia andromeda tiene millones de estrellas brillantes",
                   "observar saturno y sus anillos con un telescopio",
                   "las estrellas y planetas del sistema solar orbitan",
                   "nebulosa galaxia estrellas telescopio espacial hubble"],
    "futbol": ["partido de futbol con gol en el ultimo minuto del arbitro",
               "el delantero marco un gol de cabeza en el estadio",
               "el arbitro pito penal y el portero atajo el balon",
               "estadio lleno para la final del campeonato de futbol",
               "entrenamiento del equipo de futbol con balon y porteria"],
}


_SIL = ["ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo"]


def _relleno():
    """8 temas de relleno con pseudo-palabras propias, para que la memoria sea realista: en una
    memoria de 3 temas, las palabras de cada tema estarían en > 15 % de los recuerdos y la
    neurona las trataría como "de relleno" (DF_MAX), igual que en el experimento."""
    temas = {}
    for k in range(8):
        palabras = [_SIL[k] + _SIL[(k + j) % 14] + _SIL[(k + 2 * j + 1) % 14] + "r" for j in range(1, 9)]
        temas[f"relleno{k}"] = [" ".join(palabras[(i + j) % 8] for j in range(5)) for i in range(5)]
    return temas


def _llenar(cz, repeticiones=3, t0=1_700_000_000.0):
    """Memoria sintética: (3 temas reales + 8 de relleno) × 5 textos × repeticiones, en orden."""
    n = 0
    for r in range(repeticiones):
        for tema, textos in list(TEMAS.items()) + list(_relleno().items()):
            for i, t in enumerate(textos):
                cz.cursor.execute(
                    "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en, sinonimos) "
                    "VALUES (?, ?, 0.5, 'activo', ?, ?)",
                    (f"{tema}_{r}_{i}", f"{t} variante {r}", t0 + n * 60.0, tema))
                n += 1
    cz.conn.commit()
    return n


@pytest.fixture()
def cz(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA_ASOCIATIVA", "1")
    na._CACHE.clear()
    c = SQLiteMemoryBioRAG(db_path=str(tmp_path / "asoc.db"))
    _llenar(c)
    return c


def _sinapsis(c, origen):
    return {(d, t): p for d, t, p in c.cursor.execute(
        "SELECT destino, tipo, peso FROM sinapsis WHERE origen = ?", (origen,)).fetchall()}


# 1 ─────────────────────────────────────────────────────────────────────────────
def test_fiel_al_experimento_11(tmp_path, monkeypatch):
    """La fuerza del motor coincide con la del experimento (agujas.py + neurona_asociativa.py).
    Memoria sin textos repetidos (repeticiones=1): con textos idénticos hay empates exactos y la
    diferencia float32/float64 cambia el desempate de la fiabilidad del tiempo. En la memoria real
    de Dennys (100 pares del examen) la diferencia máxima fue 0.003."""
    monkeypatch.setenv("BIORAG_NEURONA_ASOCIATIVA", "1")
    na._CACHE.clear()
    cz = SQLiteMemoryBioRAG(db_path=str(tmp_path / "fiel.db"))
    _llenar(cz, repeticiones=1)
    import sys
    sys.path.insert(0, EXP11)
    spec_a = importlib.util.spec_from_file_location("agujas_e11", os.path.join(EXP11, "agujas.py"))
    ag = importlib.util.module_from_spec(spec_a)
    spec_a.loader.exec_module(ag)
    filas = cz.cursor.execute("SELECT concepto, contenido, creado_en FROM largo_plazo "
                              "WHERE estado='activo' ORDER BY concepto").fetchall()
    textos = [na.texto_recuerdo(c, t) for c, t, _ in filas]
    mem = ag.Memoria(textos, orden=[f[2] for f in filas], etiquetas=None)
    rng = np.random.default_rng(0)
    pares = [tuple(sorted(rng.choice(len(filas), 2, replace=False))) for _ in range(200)]
    F = mem.agujas(pares)
    col = {n: ag.NOMBRES_TODAS.index(n) for n in ("parecido", "semantica", "rareza_max", "episodio", "etiquetas")}
    na.construir(cz.cursor)
    for k, (a, b) in enumerate(pares):
        esperado = na.fuerza_desde_agujas(*(float(F[k, col[n]]) for n in col))
        motor = na.Juez(cz.cursor, filas[a][0]).fuerza(filas[b][0])
        assert motor == pytest.approx(esperado, abs=1e-6), (filas[a][0], filas[b][0])


def test_mismo_tema_pesa_mas_que_otro_tema(cz):
    juez = na.Juez(cz.cursor, "cocina_0_0")
    mismo = [juez.fuerza(f"cocina_{r}_{i}") for r in range(3) for i in range(5) if (r, i) != (0, 0)]
    otro = [juez.fuerza(f"astronomia_{r}_{i}") for r in range(1, 3) for i in range(5)]
    assert np.mean(mismo) > np.mean(otro) + 0.1


# 2, 3, 4 ───────────────────────────────────────────────────────────────────────
def _guardar(c, concepto, contenido, syn):
    c.percibir_corto_plazo(concepto, contenido, syn, "General", None)
    auto_vincular(c, concepto, contenido)
    vincular_por_sinonimos(c, concepto, syn)
    return _sinapsis(c, concepto)


def test_mismas_sinapsis_encendida_o_apagada(tmp_path, monkeypatch):
    resultados = {}
    for modo in ("0", "1"):
        monkeypatch.setenv("BIORAG_NEURONA_ASOCIATIVA", modo)
        na._CACHE.clear()
        c = SQLiteMemoryBioRAG(db_path=str(tmp_path / f"m{modo}.db"))
        _llenar(c)
        resultados[modo] = _guardar(c, "pan_de_masa_madre", "pan casero con masa madre harina y horno", "cocina, pan")
    apagada, encendida = resultados["0"], resultados["1"]
    assert apagada, "la prueba necesita que se creen sinapsis"
    assert set(apagada) == set(encendida)                       # 2. no crea ni corta
    assert all(0.5 <= p <= 1.0 for p in encendida.values())     # 3. rango
    sin_mano = [p for (d, t), p in apagada.items() if t == "sinonimo_explicito"]
    assert sin_mano and all(p == 0.9 for p in sin_mano)         # 4. apagada = 0.9 de siempre
    sin_neu = {d: p for (d, t), p in encendida.items() if t == "sinonimo_explicito"}
    assert len(set(sin_neu.values())) > 1                       # la neurona distingue


def test_peso_ordenado_como_la_fuerza():
    fs = np.linspace(0, 1, 50)
    ps = [na.peso_desde_fuerza(f) for f in fs]
    assert ps == sorted(ps) and ps[0] == 0.5 and ps[-1] == 1.0
    assert na.peso_desde_fuerza(0.6) == pytest.approx(0.80)


# 5 ─────────────────────────────────────────────────────────────────────────────
def test_si_falla_se_aparta_y_el_guardado_sigue(cz, monkeypatch):
    def explota(*a, **k):
        raise RuntimeError("falla a propósito")
    monkeypatch.setattr(na.Juez, "agujas", explota)
    s = _guardar(cz, "pan_integral", "pan integral con harina y horno", "cocina")
    assert s
    assert all(p == 0.9 for (d, t), p in s.items() if t == "sinonimo_explicito")


def test_si_falla_la_construccion_se_aparta(cz, monkeypatch):
    def explota(*a, **k):
        raise RuntimeError("falla a propósito")
    monkeypatch.setattr(na, "estado", explota)
    s = _guardar(cz, "pan_frances", "pan frances con harina y horno", "cocina")
    assert s and all(p == 0.9 for (d, t), p in s.items() if t == "sinonimo_explicito")


# 6 ─────────────────────────────────────────────────────────────────────────────
def test_nunca_baja_una_sinapsis_existente(cz):
    cz.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                      "VALUES ('pan_dulce', 'cocina_0_1', 0.97, 'manual', 1)")
    cz.conn.commit()
    s = _guardar(cz, "pan_dulce", "pan dulce con harina azucar y horno", "cocina")
    assert s[("cocina_0_1", "manual")] == pytest.approx(0.97)


# 7 ─────────────────────────────────────────────────────────────────────────────
def test_memoria_minima_usa_peso_a_mano(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA_ASOCIATIVA", "1")
    na._CACHE.clear()
    c = SQLiteMemoryBioRAG(db_path=str(tmp_path / "chica.db"))
    c.cursor.execute("INSERT INTO largo_plazo (concepto, contenido, estado, sinonimos) "
                     "VALUES ('unico_pan', 'pan con harina', 'activo', 'pan')")
    c.conn.commit()
    s = _guardar(c, "otro_pan", "pan casero con harina", "pan")
    assert s and all(p == 0.9 for (d, t), p in s.items() if t == "sinonimo_explicito")


def test_memoria_vacia_no_rompe(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA_ASOCIATIVA", "1")
    na._CACHE.clear()
    c = SQLiteMemoryBioRAG(db_path=str(tmp_path / "vacia.db"))
    assert na.estado(c.cursor) is None
    assert na.Juez(c.cursor, "x").fuerza("y") is None
    _guardar(c, "primer_recuerdo", "el primer recuerdo de todos", "inicio")


# 8 ─────────────────────────────────────────────────────────────────────────────
def test_estado_se_rehace_solo_al_crecer(cz):
    e1 = na.estado(cz.cursor)
    sello1 = dict(cz.cursor.execute("SELECT clave, valor FROM neurona_asociativa_estado").fetchall())["sello"]
    assert na.estado(cz.cursor) is e1                              # sin cambios: misma caché
    n = cz.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    for i in range(int(n * na.CRECER) + 12):
        cz.cursor.execute("INSERT INTO largo_plazo (concepto, contenido, estado, creado_en) "
                          "VALUES (?, 'nuevo recuerdo de prueba sobre pan y horno', 'activo', ?)",
                          (f"nuevo_{i}", 1_800_000_000.0 + i))
    cz.conn.commit()
    na.estado(cz.cursor)
    sello2 = dict(cz.cursor.execute("SELECT clave, valor FROM neurona_asociativa_estado").fetchall())["sello"]
    assert sello1 != sello2


def test_estado_persiste_entre_procesos(cz):
    na.estado(cz.cursor)
    juez = na.Juez(cz.cursor, "cocina_0_0")
    f1 = juez.fuerza("cocina_1_0")
    na._CACHE.clear()                                              # como un proceso nuevo
    f2 = na.Juez(cz.cursor, "cocina_0_0").fuerza("cocina_1_0")
    assert f1 == pytest.approx(f2, abs=1e-6)


def test_muestra_tiene_techo(cz, monkeypatch):
    monkeypatch.setattr(na, "MUESTRA_MAX", 20)
    est = na.construir(cz.cursor)
    assert est.n == 20


# 9 ─────────────────────────────────────────────────────────────────────────────
def test_guardia_de_tiempo(cz):
    est = na.estado(cz.cursor)
    if est.fiab_episodio <= 0:
        pytest.skip("en esta memoria el tiempo no coincide con el texto: episodio apagado")
    j = na.Juez(cz.cursor, "cocina_0_0")
    assert j.agujas("cocina_0_1")[3] > 0                           # guardados 1 minuto después
    cz.cursor.execute("UPDATE largo_plazo SET creado_en = creado_en + 30*86400 WHERE concepto = 'cocina_0_1'")
    cz.conn.commit()
    j = na.Juez(cz.cursor, "cocina_0_0")
    assert j.agujas("cocina_0_1")[3] == 0.0                        # 30 días después: no


def test_decision_rapida(cz):
    na.estado(cz.cursor)
    j = na.Juez(cz.cursor, "cocina_0_0")
    t = time.perf_counter()
    for r in range(3):
        for tema in TEMAS:
            for i in range(5):
                j.fuerza(f"{tema}_{r}_{i}")
    por_par = (time.perf_counter() - t) / 45
    assert por_par < 0.01, f"{por_par * 1000:.2f} ms por par"
