"""Neurona (core/memory/neurona.py): cada prueba es una falla concreta que debe estar cubierta.

Grupos:
  A. No daña el motor (DB vacía, sin campeón = idéntico, R@5 intocable, identidad, silencio).
  B. Aprende de verdad (asciende con datos, techo, despierta, piso que retira).
  C. No memoriza (guardia, tope por recuerdo, sin duplicados, olvidados se purgan).
  D. Fallas del sistema (pesos rotos, estado corrupto, motor cambiado, DB de solo
     lectura, varios procesos, varios hilos, cortacircuitos, ganchos que nunca rompen).
  E. Costo fijo (número de búsquedas acotado, presupuesto de tiempo).
"""
import json
import sqlite3
import threading
import time

import numpy as np
import pytest

from core import memory_service
from core.memory import neurona as N
from core.memory.neurona_examen import preguntas
from core.memory_store import SQLiteMemoryBioRAG

NODOS = [
    ("receta_pan_casero", "Amasar harina, agua, sal y levadura. Dejar levar dos horas y hornear a 220 grados."),
    ("configuracion_servidor_nginx", "El servidor nginx escucha en el puerto 80 y redirige a la aplicacion en el 8000."),
    ("leccion_backup_base_datos", "Hacer copia de la base de datos cada noche; restaurar probando en otra maquina."),
    ("error_timeout_api_pagos", "La API de pagos corta a los 30 segundos; reintentar con espera exponencial."),
    ("cumpleanos_hermana_marzo", "Mi hermana cumple el 14 de marzo; le gustan las orquideas y el chocolate amargo."),
    ("plan_entrenamiento_correr", "Correr tres veces por semana: series cortas el martes y fondo largo el domingo."),
    ("arquitectura_memoria_agente", "La memoria del agente separa corto plazo y largo plazo con consolidacion nocturna."),
    ("prueba_unitaria_login", "Las pruebas del login cubren clave vacia, usuario bloqueado y token vencido."),
    ("viaje_merida_montana", "Ruta a Merida por la montana; llevar abrigo porque de noche baja a cinco grados."),
    ("fix_cache_redis_expira", "La cache en redis expiraba antes de tiempo por un TTL en segundos y no en minutos."),
    ("principio_un_cambio_a_la_vez", "Cambiar una sola cosa por vez y medir antes y despues para saber que funciono."),
    ("contrato_alquiler_oficina", "El alquiler de la oficina vence en diciembre; aviso con sesenta dias de anticipo."),
]


def _aprender_todo(c):
    for k, v in NODOS:
        memory_service.aprender(c, k, v)


@pytest.fixture
def chica(tmp_path, monkeypatch):
    """DB pequeña creada desde cero (la neurona apagada mientras se construye, para que sea rápida)."""
    monkeypatch.delenv("BIORAG_NO_LOG", raising=False)
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    c = SQLiteMemoryBioRAG(str(tmp_path / "chica.db"))
    _aprender_todo(c)
    monkeypatch.setenv("BIORAG_NEURONA", "1")
    yield c
    c.cerrar_sistema()


def _campeon_rasgo0(fuerza=3.0):
    """Campeón a mano: sube a quien tenga alto el rasgo 0 (bm25)."""
    W = np.zeros((N.OCULTAS, len(N.F_SIG)))
    W[0, 0] = 5.0
    return {"W": W, "b": np.zeros(N.OCULTAS), "v": np.array([fuerza] + [0.0] * (N.OCULTAS - 1))}


def _caso(rng, cat, nodo, y=1, delator=None, n=8, base=None):
    """Caso sintético: la fórmula pone la respuesta en el puesto y+1; el rasgo 0 delata a `delator`."""
    X = (rng.random((n, len(N.F_SIG))) * 0.2).astype(np.float32)
    X[delator if delator is not None else y, 0] = 1.0
    base = np.array(base or [2.0, 1.9, 1.0, .5, 0, -.5, -1, -1.5][:n], dtype=np.float32)
    return dict(cat=cat, nodo=nodo, q=f"q{rng.random():.12f}", y=y, X=X, base=base)


def _pagina(nombres, scores):
    return [(n, "contenido", 1.0, "activo", s, "") for n, s in zip(nombres, scores)]


def _v(pag, rasgos):
    """La vista que search.py entrega a la neurona para esta página (sin convergencia ni agente)."""
    return N.vista(pag, rasgos, {}, {}, {}, con_peso=False, con_agente=False)


# ───────────────────────── A. no daña el motor ─────────────────────────

def test_db_vacia_no_falla(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "vacia.db"))
    try:
        res = N.practicar(c, [])
        assert res["fase"] == "juntando examen" and res["nuevas"] == 0 and res["campeon"] is False
        r, _ = c.buscar_por_frase("cualquier cosa", limite=5)
        assert isinstance(r, list)
    finally:
        c.cerrar_sistema()


def test_sin_campeon_la_busqueda_es_identica(chica, monkeypatch):
    for _ in range(3):
        N.practicar(chica, [])  # junta examen; con 12 nodos no alcanza para un campeón
    assert N.estado(chica).campeon is None
    for q in ("pan casero", "servidor puerto", "copia base de datos noche", "hermana marzo"):
        monkeypatch.setenv("BIORAG_NEURONA", "0")
        a, _ = chica.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)
        monkeypatch.setenv("BIORAG_NEURONA", "1")
        b, _ = chica.buscar_por_frase(q, limite=5, ignore_peso_sinaptico=True)
        assert [(r[0], r[4]) for r in a] == [(r[0], r[4]) for r in b]


def test_reordenar_solo_permuta_el_top5(chica):
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0()
    nombres = [f"n{i}" for i in range(8)]
    scores = [.95, .9, .85, .8, .75, .7, .65, .6]
    rasgos = {n: ([0.0] * len(N.F_FORMULA), s) for n, s in zip(nombres, scores)}
    rasgos["n3"] = ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .8)   # el rasgo 0 delata a n3
    rasgos["n6"] = ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .65)  # n6 está FUERA del top-5
    pag = _pagina(nombres, scores)
    nuevo = N.reordenar(chica, "consulta cualquiera", pag, _v(pag, rasgos))
    assert nuevo[0][0] == "n3"                                   # la neurona sí actúa
    assert sorted(r[0] for r in nuevo[:5]) == sorted(nombres[:5])  # mismos nodos en el top-5
    assert [r[4] for r in nuevo[:5]] == scores[:5]               # mismos números, en orden
    assert nuevo[5:] == pag[5:]                                  # lo de abajo, intacto


def test_mcp_ve_los_mismos_numeros_por_posicion(chica):
    """El MCP decide ráfaga/certeza con last_score_base_map del #1: tras reordenar, cada
    posición debe conservar sus números (base y bonus), solo cambia el recuerdo."""
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0()
    nombres = ["n0", "n1", "n2"]
    rasgos = {"n0": ([0.0] * len(N.F_FORMULA), .9), "n1": ([0.0] * len(N.F_FORMULA), .8),
              "n2": ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .7)}
    chica.last_score_base_map = {"n0": .88, "n1": .79, "n2": .61}
    chica.last_score_bonus_map = {"n0": .02, "n1": .01}
    pag = _pagina(nombres, [.9, .8, .7])
    nuevo = N.reordenar(chica, "x", pag, _v(pag, rasgos))
    orden = [r[0] for r in nuevo]
    assert orden[0] == "n2"
    assert [chica.last_score_base_map[c] for c in orden] == [.88, .79, .61]
    assert [chica.last_score_bonus_map.get(c) for c in orden] == [.02, .01, None]


def test_regla_de_identidad(chica):
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0(fuerza=50.0)
    nombres = ["caso_conflicto_liderazgo", "otro", "tercero"]
    rasgos = {"caso_conflicto_liderazgo": ([0.0] * len(N.F_FORMULA), .9),
              "otro": ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .8), "tercero": ([0.0] * len(N.F_FORMULA), .7)}
    pag = _pagina(nombres, [.9, .8, .7])
    assert N.reordenar(chica, "Caso conflicto  liderazgo", pag, _v(pag, rasgos))[0][0] == "caso_conflicto_liderazgo"
    assert N.reordenar(chica, "conflicto", pag, _v(pag, rasgos))[0][0] == "otro"


def test_practica_es_silenciosa(chica):
    contar = lambda t: chica.cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: E731
    chica.buscar_por_frase("pan casero", limite=5)
    antes_attrs = {k: v for k, v in chica.__dict__.items() if k.startswith("last_")}
    log0, acc0 = contar("log_busquedas"), contar("nodo_accesos_historial")
    for _ in range(3):
        N.practicar(chica, [])
    assert contar("log_busquedas") == log0
    assert contar("nodo_accesos_historial") == acc0
    despues = {k: v for k, v in chica.__dict__.items() if k.startswith("last_")}
    assert despues.keys() == antes_attrs.keys() and all(despues[k] is antes_attrs[k] for k in despues)
    chica.buscar_por_frase("servidor nginx", limite=5)       # control: una búsqueda real sí se registra
    assert contar("log_busquedas") == log0 + 1


def test_apagada(chica, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    assert N.practicar(chica, [])["fase"] == "apagada"
    N.estado(chica).campeon = _campeon_rasgo0()
    assert N.necesita_rasgos(chica) is False


# ───────────────────────── B. aprende de verdad ─────────────────────────

def _estado_sintetico(n_estudio=200, n_guardia=60, semilla=1):
    rng = np.random.default_rng(semilla)
    est = N._Estado()
    est.estudio = [_caso(rng, "a", f"e{i}") for i in range(n_estudio)]
    est.guardia = [_caso(rng, "a", f"g{i}") for i in range(n_guardia)]
    return est, rng


def test_aprende_asciende_llega_al_techo_y_despierta(monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA_PACIENCIA", "4")
    monkeypatch.setenv("BIORAG_NEURONA_DESPERTAR", "50")
    est, rng = _estado_sintetico()
    cfg = N._cfg()
    assert N._r1(None, est.guardia, 5).sum() == 0          # a mano no acierta ninguna
    fases = [N._evaluar_y_decidir(est, cfg)["fase"] for _ in range(30)]
    assert "ascenso" in fases and est.campeon is not None
    assert N._r1(est.campeon, est.guardia, 5).mean() > .9   # aprendió algo que GENERALIZA a la guardia
    assert est.stats["tranquila"] is True                   # techo: dejó de entrenar
    assert N._evaluar_y_decidir(est, cfg)["fase"] == "tranquila"
    est.stats["nuevas_desde_tranquila"] = 60                 # entraron preguntas nuevas
    assert N._evaluar_y_decidir(est, cfg)["fase"] != "tranquila"


def test_memoriza_lo_estudiado_pero_la_guardia_lo_delata():
    """El estudio premia el rasgo 0, pero en la guardia ese rasgo señala a un intruso: lo
    aprendido no generaliza. No debe ascender nunca y debe reiniciarse (anti-memorización)."""
    rng = np.random.default_rng(5)
    est = N._Estado()
    est.estudio = [_caso(rng, "a", f"e{i}") for i in range(200)]
    est.guardia = [_caso(rng, "a", f"g{i}", y=0, delator=1) for i in range(60)]
    res = [N._evaluar_y_decidir(est, N._cfg()) for _ in range(15)]
    assert any(r.get("reinicio") for r in res)
    assert all(r["fase"] != "ascenso" for r in res) and est.campeon is None and est.margen == 0.0


def _estado_mixto(n_a, n_b, semilla=2, base_b=None):
    """cat "a": el rasgo 0 delata a la respuesta (puesto 2). cat "b": la fórmula acierta y el
    rasgo 0 delata a un INTRUSO: un campeón que sube el rasgo 0 rompe "b"."""
    rng = np.random.default_rng(semilla)
    est = N._Estado()
    est.estudio = [_caso(rng, "a", f"a{i}") for i in range(n_a)] + \
                  [_caso(rng, "b", f"b{i}", y=0, delator=1, base=base_b) for i in range(n_b)]
    est.guardia = [_caso(rng, "a", f"ga{i}") for i in range(n_a // 4)] + \
                  [_caso(rng, "b", f"gb{i}", y=0, delator=1, base=base_b) for i in range(max(1, n_b // 4))]
    return est


def _danos(est, p, margen):
    todos = est.estudio + est.guardia
    h, c = N._rangos(None, todos, 5) == 1, N._rangos(p, todos, 5, margen) == 1
    return int((h & ~c)[len(est.estudio):].sum()), int((h & ~c).sum()), int((~h & c).sum())


def test_campeon_que_dana_una_categoria_sube_su_margen_o_se_retira():
    est = _estado_mixto(150, 30)
    est.campeon = _campeon_rasgo0()
    assert _danos(est, est.campeon, 0.0)[1] > 0                 # sin margen, daña a "b"
    res = N._evaluar_y_decidir(est, N._cfg())
    if est.campeon is not None and not res.get("retiro"):
        dg, dt, gt = _danos(est, est.campeon, est.margen)
        assert dg == 0 and dt <= 0.05 * gt                      # con su margen ya no daña
        todos = est.estudio + est.guardia
        cat_b = N._por_cat(N._rangos(est.campeon, todos, 5, est.margen), todos)["b"]
        assert cat_b[0] == sum(c["cat"] == "b" for c in todos)  # "b" intacta


def test_campeon_que_solo_dana_se_retira():
    est = _estado_mixto(0, 200)                                  # solo hay casos que el rasgo 0 rompe
    est.campeon = _campeon_rasgo0()
    res = N._evaluar_y_decidir(est, N._cfg())
    assert res.get("retiro") is True and est.campeon is None and est.margen == 0.0


def test_primero_no_danar_elige_el_menor_margen_seguro():
    # gana en casos ajustados ("a": la fórmula duda, 2.0 vs 1.9) y daña donde la fórmula
    # estaba SEGURA ("b": 2.0 vs 0.0): justo lo que un margen debe separar
    est = _estado_mixto(400, 40, base_b=[2.0, 0.0, -.5, -1, -1.5, -2, -2.5, -3])
    todos = est.estudio + est.guardia
    r_mano = N._rangos(None, todos, 5)
    m, _ = N._calibrar(_campeon_rasgo0(), todos, len(est.estudio), r_mano, N._por_cat(r_mano, todos),
                       0, int((r_mano == 1).sum()) + 1, 5)
    assert m is not None and m > 0                               # necesitó margen para no dañar
    i = N.MARGENES.index(m)
    dg, dt, gt = _danos(est, _campeon_rasgo0(), m)
    assert dg == 0 and dt <= 0.05 * gt and gt > 0                # no daña y sigue ganando
    dg0, dt0, gt0 = _danos(est, _campeon_rasgo0(), N.MARGENES[i - 1])
    piso_ok = N._cumple_piso(N._por_cat(N._rangos(_campeon_rasgo0(), todos, 5, N.MARGENES[i - 1]), todos),
                             N._por_cat(r_mano, todos))
    assert dg0 > 0 or dt0 > 0.05 * gt0 or not piso_ok            # y es el menor: con el anterior dañaba


def test_el_margen_se_respeta_al_servir(chica):
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0(fuerza=1.0)                    # corrección máxima ~ +1
    rasgos = {"a": ([0.0] * len(N.F_FORMULA), .80), "b": ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .79)}
    pag = _pagina(["a", "b"], [.80, .79])
    est.margen = 0.0
    assert N.reordenar(chica, "x", pag, _v(pag, rasgos))[0][0] == "b"
    est.margen = 2.0                                              # no le alcanza la ventaja: no toca
    assert N.reordenar(chica, "x", pag, _v(pag, rasgos)) == pag


def test_sin_datos_suficientes_no_entrena():
    est, _ = _estado_sintetico(n_estudio=20, n_guardia=5)
    assert N._evaluar_y_decidir(est, N._cfg())["fase"] == "juntando examen"
    assert est.campeon is None


# ───────────────────────── C. no memoriza ─────────────────────────

def test_un_recuerdo_no_acapara_el_examen():
    rng = np.random.default_rng(3)
    lista, r = [], __import__("random").Random(0)
    for i in range(100):
        N._meter(lista, _caso(rng, "a", "el_mismo"), 50, r, 4)  # guardado 100 veces
    assert sum(c["nodo"] == "el_mismo" for c in lista) <= 4
    c = _caso(rng, "a", "otro")
    N._meter(lista, c, 50, r, 4)
    c2 = dict(c, y=2)
    N._meter(lista, c2, 50, r, 4)                                   # misma pregunta: reemplaza
    assert sum(x["nodo"] == "otro" for x in lista) == 1 and c2 in lista


def test_la_guardia_es_estable_y_cerca_del_20_por_ciento():
    nombres = [f"recuerdo_{i}" for i in range(5000)]
    frac = sum(N._es_guardia(n) for n in nombres) / len(nombres)
    assert .17 < frac < .23
    assert all(N._es_guardia(n) == N._es_guardia(n) for n in nombres[:50])


def test_recuerdos_olvidados_salen_del_examen(chica):
    rng = np.random.default_rng(4)
    est = N.estado(chica)
    est.estudio = [_caso(rng, "a", "no_existe_mas") for _ in range(5)] + [_caso(rng, "a", "receta_pan_casero")]
    N._purgar_olvidados(chica, est, __import__("random").Random(0), n=50)
    assert [c["nodo"] for c in est.estudio] == ["receta_pan_casero"]


def test_autoexamen_determinista_y_con_contenido():
    a = preguntas("error_timeout_api_pagos", NODOS[3][1])
    assert a == preguntas("error_timeout_api_pagos", NODOS[3][1])
    cats = {c for c, _ in a}
    assert "contenido" in cats
    assert all(q.lower() != "error timeout api pagos" for _, q in a)


# ───────────────────────── D. fallas del sistema ─────────────────────────

def test_pesos_rotos_no_se_usan_ni_se_cargan(chica):
    est = N.estado(chica)
    roto = _campeon_rasgo0()
    roto["v"][0] = np.nan
    est.campeon = roto
    rasgos = {n: ([1.0] * len(N.F_FORMULA), s) for n, s in (("a", .9), ("b", .8))}
    pag = _pagina(["a", "b"], [.9, .8])
    assert N.reordenar(chica, "x", pag, _v(pag, rasgos)) == pag
    N._guardar(chica, est)
    chica._neurona_estado = None
    assert N.estado(chica).campeon is None


def test_entrenamiento_que_diverge_se_descarta(monkeypatch):
    est, _ = _estado_sintetico()
    monkeypatch.setenv("BIORAG_NEURONA_LR", "1e9")
    monkeypatch.setattr(N, "_paso", lambda est, P, lr, l2: est.retador.__setitem__("v", est.retador["v"] * np.nan))
    res = N._evaluar_y_decidir(est, N._cfg())
    assert res.get("divergio") is True and N._sano(est.retador) and est.campeon is None


def test_estado_corrupto_arranca_limpio(chica):
    N._tabla(chica)
    chica.cursor.executemany("INSERT OR REPLACE INTO neurona_estado VALUES (?, ?, ?)",
                             [("pesos", "{esto no es json", time.time()), ("memoria", b"\x00basura", time.time())])
    chica.conn.commit()
    chica._neurona_estado = None
    est = N.estado(chica)
    assert est.campeon is None and est.estudio == []
    assert N.practicar(chica, [])["guardado"] is True


def test_el_margen_se_guarda_y_uno_corrupto_no_se_usa(chica, monkeypatch):
    est = N.estado(chica)
    est.campeon, est.margen = _campeon_rasgo0(), 1.5
    assert N._guardar(chica, est) is True
    chica._neurona_estado = None
    assert N.estado(chica).margen == 1.5 and N.estado(chica).campeon is not None
    for malo in (-1.0, float("nan"), 1e9, "abc"):              # negativo = MÁS atrevida: prohibido
        fila = json.loads(chica.cursor.execute("SELECT valor FROM neurona_estado WHERE clave='pesos'").fetchone()[0])
        fila["margen"] = malo
        chica.cursor.execute("UPDATE neurona_estado SET valor=? WHERE clave='pesos'", (json.dumps(fila),))
        chica.conn.commit()
        chica._neurona_estado = None
        assert N.estado(chica).campeon is None, malo             # estado dudoso: vuelve a los pesos a mano
    est = N.estado(chica)
    est.margen = 2.0
    for env, esperado in (("-3", 2.0), ("nan", 2.0), ("x", 2.0), ("", 2.0), ("0.5", 0.5)):
        monkeypatch.setenv("BIORAG_NEURONA_MARGEN", env)
        assert N._margen_servir(est) == esperado, env


def test_si_cambia_la_formula_del_motor_se_reaprende(chica, monkeypatch):
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0()
    N._guardar(chica, est)
    chica._neurona_estado = None
    assert N.estado(chica).campeon is not None                  # mismo motor: se conserva
    original = chica._calcular_score_hibrido
    monkeypatch.setattr(chica, "_calcular_score_hibrido", lambda **kw: original(**kw) * 0.9)
    chica._neurona_estado = None
    est2 = N.estado(chica)
    assert est2.campeon is None and est2.stats["descartes"] >= 1  # motor distinto: no usa lo viejo


def test_db_de_solo_lectura_no_rompe(chica, tmp_path):
    ruta = chica.db_path
    chica.conn.commit()
    ro = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True, check_same_thread=False)
    chica.conn, chica.cursor = ro, ro.cursor()
    res = N.practicar(chica, [])
    assert isinstance(res, dict) and res.get("guardado") in (False, None)


def test_varios_procesos_sobre_la_misma_db(chica):
    chica.conn.commit()  # consolidar_concepto deja su último INSERT sin commit (comportamiento previo del motor)
    otro = SQLiteMemoryBioRAG(chica.db_path)
    try:
        assert N.estado(otro).campeon is None
        est = N.estado(chica)
        est.campeon = _campeon_rasgo0()
        time.sleep(0.01)
        N._guardar(chica, est)
        assert N._refrescar(otro, forzar=True).campeon is not None
    finally:
        otro.cerrar_sistema()


def test_silencio_es_por_hilo(chica):
    visto = {}
    with N._en_silencio(chica):
        assert N.silencio(chica)
        t = threading.Thread(target=lambda: visto.setdefault("otro_hilo", N.silencio(chica)))
        t.start()
        t.join()
    assert visto["otro_hilo"] is False and not N.silencio(chica)


def test_dos_practicas_a_la_vez_no_se_bloquean(chica):
    candado = N._candado(chica)
    candado.acquire()
    try:
        t0 = time.time()
        assert N.practicar(chica, [])["fase"] == "ocupada"
        assert time.time() - t0 < 0.5
    finally:
        candado.release()


def test_cortacircuitos_tras_tres_fallas(chica, monkeypatch):
    def explota(*a, **k):
        raise RuntimeError("falla simulada")
    monkeypatch.setattr(N, "_nodos_a_examinar", explota)
    assert [N.practicar(chica, [])["fase"] for _ in range(3)] == ["error"] * 3
    assert N.practicar(chica, [])["fase"] == "en pausa por fallas"
    assert chica.consolidar_concepto("receta_pan_casero") in (True, False)  # el motor sigue


def test_los_ganchos_nunca_rompen_la_escritura(chica, monkeypatch):
    def explota(*a, **k):
        raise RuntimeError("neurona caída")
    monkeypatch.setattr(N, "practicar", explota)
    memory_service.aprender(chica, "nodo_nuevo_tras_falla", "contenido nuevo para guardar igual")
    assert chica.cursor.execute("SELECT 1 FROM largo_plazo WHERE concepto = 'nodo_nuevo_tras_falla'").fetchone()
    chica.ciclo_sueno_consolidacion()


def test_los_ganchos_disparan_la_practica(chica, monkeypatch):
    llamadas = []
    monkeypatch.setattr(N, "practicar", lambda self, conceptos=(), **k: llamadas.append(list(conceptos)))
    memory_service.aprender(chica, "nodo_gancho", "contenido para el gancho de consolidar")
    assert ["nodo_gancho"] in llamadas
    chica.percibir_corto_plazo("nodo_sueno", "contenido que se consolida en el sueño", "", "General")
    chica.ciclo_sueno_consolidacion()
    assert any("nodo_sueno" in l for l in llamadas)


# ───────────────────────── E. costo fijo ─────────────────────────

def test_numero_de_busquedas_acotado(chica, monkeypatch):
    llamadas = []
    original = chica.buscar_por_frase
    monkeypatch.setattr(chica, "buscar_por_frase", lambda *a, **k: (llamadas.append(1), original(*a, **k))[1])
    cfg = N._cfg()
    N.practicar(chica, [k for k, _ in NODOS] * 10, presupuesto_s=60)  # 120 "recién guardados"
    assert len(llamadas) <= cfg["nodos"] * cfg["preguntas"]


def test_presupuesto_de_tiempo(chica):
    t0 = time.time()
    res = N.practicar(chica, [], presupuesto_s=0.0)
    assert res["nuevas"] == 0 and time.time() - t0 < 2.0


# ───────────────── F. desfase 0: estudia lo mismo que sirve (experimento 07) ─────────────────

def _vista_servida(c, monkeypatch, consulta, **kw):
    """Búsqueda NORMAL; captura la vista exacta que search.py le pasa a reordenar."""
    vistas = []
    real = N.reordenar

    def espia(self, frase, pagina, v):
        vistas.append(v)
        return real(self, frase, pagina, v)
    monkeypatch.setattr(N, "reordenar", espia)
    c.buscar_por_frase(consulta, profundidad="activos", **kw)
    monkeypatch.setattr(N, "reordenar", real)
    return vistas[-1]


@pytest.mark.parametrize("modo", N.MODOS)
def test_el_examen_ve_exactamente_lo_que_se_sirve(chica, monkeypatch, modo):
    from core.memory.neurona_examen import sustantivos_de
    q = "insight backup repository inputs"          # devuelve varios recuerdos: hay qué ordenar
    caso = N._preguntar(chica, "leccion_backup_base_datos", q, "literal", modo, 10)
    assert caso is not None and caso["cat"] == f"literal@{modo}"
    if modo == "agente":
        kw = dict(limite=30, convergencia_limite=10, sustantivos_clave_boost=sustantivos_de(q))
    else:
        kw = dict(limite=5, ignore_peso_sinaptico=True)
    N.estado(chica).campeon = _campeon_rasgo0(fuerza=0.0)    # neutro: obliga a servir con vista sin mover nada
    v = _vista_servida(chica, monkeypatch, q, **kw)
    assert v["nombres"][caso["y"]] == "leccion_backup_base_datos" and len(v["nombres"]) >= 2
    assert np.array_equal(v["X"], caso["X"]) and np.array_equal(v["base"], caso["base"])
    assert v["X"][0, N.F_SIG.index("con_agente")] == (1.0 if modo == "agente" else 0.0)
    assert v["X"][0, N.F_SIG.index("con_peso")] == (1.0 if modo == "agente" else 0.0)


def test_la_vista_de_otra_pagina_no_reordena(chica):
    est = N.estado(chica)
    est.campeon = _campeon_rasgo0(fuerza=50.0)
    rasgos = {"a": ([0.0] * len(N.F_FORMULA), .9), "b": ([1.0] + [0.0] * (len(N.F_FORMULA) - 1), .8)}
    pag = _pagina(["a", "b"], [.9, .8])
    otra = _pagina(["b", "a"], [.9, .8])
    assert N.reordenar(chica, "x", otra, _v(pag, rasgos)) == otra   # vista ajena: no toca
    assert N.reordenar(chica, "x", pag, None) == pag                 # sin vista: no toca


def test_nodo_sin_rasgos_va_en_cero_con_bandera_y_senales_del_agente():
    pag = _pagina(["hub", "b"], [.9, .8])
    v = N.vista(pag, {"b": ([.5] * len(N.F_FORMULA), .8)}, {"hub": ("concept_hub", 1.0)},
                {"b": .085}, {"b": {"concepto": 1.0, "sustantivos_clave": .5}},
                con_peso=True, con_agente=True)
    f = dict(zip(N.F_SIG, v["X"][0]))
    assert all(f[n] == 0.0 for n in N.F_FORMULA) and f["sin_rasgos"] == 1.0 and f["or_hub"] == 1.0
    f = dict(zip(N.F_SIG, v["X"][1]))
    assert f["sin_rasgos"] == 0.0 and f["bono_conv"] == pytest.approx(1.0) and f["ev_sustantivos"] == .5
    assert f["con_agente"] == 1.0 and f["peso"] == 1.0
    assert N.vista(_pagina(["solo"], [.9]), {}, {}, {}, {}, True, True) is None   # 1 resultado: nada que ordenar
    assert N.vista([("x", "", "roto", "activo", .9, "")] * 2, {}, {}, {}, {}, True, True) is None  # nunca lanza


def test_practica_los_dos_caminos(chica, monkeypatch):
    modos, real = [], N._preguntar

    def espia(self, concepto, q, cat, modo="crudo", limite_agente=10):
        modos.append(modo)
        return real(self, concepto, q, cat, modo, limite_agente)
    monkeypatch.setattr(N, "_preguntar", espia)
    for _ in range(3):
        N.practicar(chica, [k for k, _ in NODOS[:6]])
    assert set(modos) == set(N.MODOS) and abs(modos.count("agente") - modos.count("crudo")) <= 2
    est = N.estado(chica)
    assert all(c["X"].shape[1] == len(N.F_SIG) and len(c["base"]) <= N._cfg()["topk"] for c in est.estudio + est.guardia)


def test_sustantivos_del_agente_salen_de_la_consulta():
    from core.memory.neurona_examen import sustantivos_de
    assert sustantivos_de("¿Cómo se configura el servidor de correo?") == "configura,servidor,correo"
    assert sustantivos_de("de la el") == ""
    assert all(len(t) <= 15 for t in sustantivos_de("supercalifragilisticoespialidoso palabra").split(","))


def test_la_vista_cubre_lo_que_vera_quien_busca_con_tope():
    nombres = [f"n{i}" for i in range(14)]
    pag = _pagina(nombres, [1.0 - i * .05 for i in range(14)])
    assert len(N.vista(pag, {}, {}, {}, {}, True, True)["nombres"]) == 5            # sin dato: topk
    assert len(N.vista(pag, {}, {}, {}, {}, True, True, k=10)["nombres"]) == 10     # el MCP muestra 10
    assert len(N.vista(pag, {}, {}, {}, {}, True, True, k=500)["nombres"]) == N._cfg()["topk_max"]  # costo fijo


def test_con_vista_de_10_el_r5_no_puede_bajar():
    """Un campeón que gana #1 en el estudio pero en la guardia empuja la respuesta del
    puesto 5 al 6: con vistas de 10 eso bajaría el R@5. Ningún margen aceptado puede
    sacar del top-5 a un caso de guardia que la fórmula tenía adentro."""
    rng = np.random.default_rng(11)
    estudio = [_caso(rng, "a", f"e{i}", y=1, n=8) for i in range(200)]
    guardia = [_caso(rng, "a", f"g{i}", y=4, delator=5, n=8) for i in range(60)]
    todos = estudio + guardia
    r_mano = N._rangos(None, todos, 10)
    p = _campeon_rasgo0(fuerza=3.0)
    m, r = N._calibrar(p, todos, len(estudio), r_mano, N._por_cat(r_mano, todos), 0, 0, 10)
    assert m is not None and m > 0                         # el margen 0 (que ganaba 200 #1) se rechaza
    t5_mano, t5 = (r_mano >= 1) & (r_mano <= 5), (r >= 1) & (r <= 5)
    assert not (t5_mano & ~t5)[len(estudio):].any()
    sin = N._rangos(p, todos, 10, 0.0)                     # sin margen sí lo sacaría: la capa es necesaria
    assert (r_mano[len(estudio):] == 5).all() and (sin[len(estudio):] > 5).sum() >= 10
