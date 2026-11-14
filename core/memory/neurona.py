"""Neurona de BioRAG: aprende sola, en vivo, a ordenar mejor el top-5.

QUÉ ES
    Una pequeña red (29 señales -> 6 neuronas ocultas -> 1 corrección) que se
    SUMA a la fórmula a mano de `scoring.py`. Las 29 señales: las 17 agujas de la
    fórmula + 12 de lo que pasa después de ella y de lo que aporta el agente
    (bono y evidencia de convergencia, sustantivos_clave, peso, origen). Con la corrección en cero el motor
    es exactamente el de siempre: los pesos a mano son el ancla y el piso.

CUÁNDO APRENDE (en vivo, costo fijo)
    Al consolidar un recuerdo, porque ahí sí se sabe la respuesta correcta.
    El recuerdo se hace sus propias preguntas (`neurona_examen.py`), el motor las
    responde en silencio (sin log, sin accesos, sin tocar el DMN) y la neurona
    aprende de lo que falló. Cada ciclo examina un número FIJO de recuerdos
    (`BIORAG_NEURONA_NODOS`, 8; `BIORAG_NEURONA_PREGUNTAS`, 7) dentro de un
    presupuesto de tiempo fijo (3 s), y la memoria de examen tiene tamaño fijo.
    El costo es el mismo con 10 o con un millón de recuerdos. Si hay menos
    recuerdos nuevos que huecos, repasa recuerdos viejos elegidos al azar por
    rowid (O(log N), sin recorrer la tabla), primero los del grupo del examen
    (estudio o guardia) al que más le faltan preguntas.

PISO Y TECHO (que aprenda, no que memorice)
    - Piso: ninguna categoría del examen puede quedar con menos aciertos que
      los pesos a mano, ni en aciertos #1 ni en MRR. Si el campeón deja de
      cumplirlo (la DB cambió), se retira y vuelven los pesos a mano.
    - Techo: el 20 % de los recuerdos (por hash del nombre) es GUARDIA y
      nunca se estudia. El retador solo asciende si mejora sin empeorar la
      guardia; si estudia mejor pero la guardia no, se reinicia y NO asciende
      ese ciclo, aunque un margen grande lo deje "sin dañar" (anti-memorización). Tras `PACIENCIA` ciclos sin mejora, la neurona queda
      "tranquila" y deja de entrenar. Si baja, o si entran muchas preguntas
      nuevas, se despierta sola.

DESFASE 0: ESTUDIA LO MISMO QUE SIRVE (experimento 07)
    Una sola función, `vista`, arma lo que ve la neurona a partir de la página
    TAL COMO SE SIRVE (después de convergencia, hub, prefijo, despertar). El
    autoexamen guarda esa vista y `reordenar` corrige esa misma vista: lo que se
    aprende y lo que se usa es idéntico por construcción, no por casualidad.
    Practica los dos caminos reales, alternando: "agente" (como llega por el MCP
    `recordar`: pool 3x, convergencia, peso, sustantivos_clave sacados de la
    consulta) y "crudo" (el motor solo, como la QA). El piso es por categoría Y
    por camino: ninguno de los dos puede bajar.
    La vista cubre lo que VERÁ quien busca: 10 por el MCP (`convergencia_limite`),
    5 si no se sabe (tope `topk_max`). Con 10, la neurona podría sacar a alguien
    del top-5, así que el piso cubre R@1, MRR y R@5, y ningún caso de guardia que
    la fórmula tenía en el top-5 puede salir de él.

CÓMO RESPONDE
    Solo reordena los k primeros que ya eligió el motor (mismos nodos, mismos
    números reasignados). El R@k no puede bajar por construcción, el R@5 lo
    protege el piso, y ningún umbral absoluto
    (GABA, abstención, FP) ve números distintos. Regla de identidad: si la
    consulta es el nombre de un recuerdo ("_" = espacio) y la fórmula ya lo
    puso #1, sigue siendo #1 (las búsquedas literales no pueden empeorar). DB vacía o sin datos suficientes: no hay campeón y el
    motor responde idéntico al de hoy.

PRIMERO NO DAÑAR (margen)
    La neurona solo puede cambiar el orden de la fórmula si su ventaja supera
    un margen ε (`MARGENES`): a cada puesto se le suma ε·(k - puesto). El margen
    es el MENOR con el que el campeón no pierde ningún caso de la guardia que la
    fórmula acertaba, pierde en total menos del 5 % de lo que gana, cumple el
    piso y sigue ganando a la fórmula. Se recalibra en cada ciclo; si ningún
    margen lo logra, el campeón se retira. Así cambia solo donde está segura y
    la fórmula dudaba. Forzar: BIORAG_NEURONA_MARGEN.

PISO CONTRA EL CAMPEÓN (experimento 08)
    El piso de la fórmula impide hundirse; no impide que un retador le gane al
    campeón en total cediendo una categoría. Por eso, además, un retador no
    asciende si en alguna categoría del examen queda por debajo del campeón
    saliente en más de `tol_campeon` casos (R@1, MRR y R@5; por defecto 1). La
    tolerancia de un caso evita que la neurona se trabe por el ruido de un
    solo caso. BIORAG_NEURONA_TOL_CAMPEON.

CAPAS DE PROTECCIÓN (cada una con su prueba en tests/test_neurona.py)
    - Silencio por hilo: el autoexamen no escribe log, accesos ni DMN, y otro
      hilo (DMN) que busca a la vez no queda en silencio.
    - Un solo aprendiz: candado no bloqueante; si está ocupada, se salta el ciclo.
    - Disyuntor: tras errores seguidos, pausa (`pausa` ciclos) y no tumba el motor.
    - Pesos sanos: NaN/Inf/explosión -> se descartan; si el entrenamiento
      diverge se vuelve a los pesos anteriores.
    - Invariante de reorden: mismos nodos, mismos números; si no, la página
      original. También se permutan los mapas de score del MCP.
    - Huella del motor: si la fórmula cambió (otra versión de BioRAG), el estado
      viejo se descarta y se empieza de cero desde los pesos a mano.
    - Estado estricto: JSON/blob corrupto o de otra forma -> estado nuevo.
    - Memoria acotada: sin duplicados y con tope por recuerdo (`tope_nodo`).
    - Presupuesto de tiempo fijo por ciclo.
    - Piso contra el campeón: un retador no le quita al campeón más de
      `tol_campeon` casos en ninguna categoría y camino.

APAGADO TOTAL: BIORAG_NEURONA=0.
Evidencia: docs/Mi neurona en el sistema/experimento_04_autoaprendizaje/, experimento_05_neurona_cableada/
experimento_06_capas_de_proteccion/, experimento_07_la_neurona_escucha/ y
experimento_08_piso_contra_el_campeon/.
"""
import hashlib
import io
import json
import logging
import math
import os
import random
import threading
import time
from contextlib import contextmanager

import numpy as np

logger = logging.getLogger(__name__)

F_FORMULA = ("bm25_norm", "dim_score", "concepto_ratio", "sinonimos_ratio", "latcad",
             "grupo_score", "tematico_g", "asoc", "pred_score", "ppmi_score", "hub_match",
             "ncd_score", "episodio_score", "campo_score", "jsd", "match_exacto", "sin95")
# Lo que pasa DESPUÉS de la fórmula y lo que aporta el agente (v2, experimento 07):
# bono de convergencia multicampo, evidencia por campo (incluye sustantivos_clave),
# peso sináptico, si el score lo incluye, si el agente ayudó, y de dónde vino el recuerdo.
F_VISTA = ("bono_conv", "ev_concepto", "ev_sinonimos", "ev_sustantivos", "ev_contenido",
           "peso", "con_peso", "con_agente", "or_lexico", "or_hub", "or_no_literal", "sin_rasgos")
F_SIG = F_FORMULA + F_VISTA
OCULTAS = 6
VERSION = 2
MODOS = ("agente", "crudo")   # agente = como llega por el MCP; crudo = motor solo (como la QA)


def _env_int(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def _env_float(nombre, defecto):
    try:
        return float(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def activa():
    return os.environ.get("BIORAG_NEURONA", "1") != "0"


def _cfg():
    return dict(
        # Cuánto practica tras cada consolidación. Topes fijos (no dependen del tamaño
        # de la DB) y además el presupuesto de tiempo corta antes si las búsquedas son
        # lentas. Todas las preguntas del recuerdo (no todas sirven: si la respuesta
        # queda fuera del top se descartan), así se llenan sus `tope_nodo` lugares.
        nodos=_env_int("BIORAG_NEURONA_NODOS", 8),
        preguntas=_env_int("BIORAG_NEURONA_PREGUNTAS", 7),
        presupuesto=_env_float("BIORAG_NEURONA_PRESUPUESTO_S", 3.0),
        limite_agente=_env_int("BIORAG_NEURONA_LIMITE_AGENTE", 10),
        max_estudio=_env_int("BIORAG_NEURONA_MAX_ESTUDIO", 1200),
        max_guardia=_env_int("BIORAG_NEURONA_MAX_GUARDIA", 300),
        min_estudio=_env_int("BIORAG_NEURONA_MIN_ESTUDIO", 150),
        min_guardia=_env_int("BIORAG_NEURONA_MIN_GUARDIA", 40),
        pasos=_env_int("BIORAG_NEURONA_PASOS", 30),
        lr=_env_float("BIORAG_NEURONA_LR", 0.03),
        l2=_env_float("BIORAG_NEURONA_L2", 1e-3),
        paciencia=_env_int("BIORAG_NEURONA_PACIENCIA", 12),
        despertar=_env_int("BIORAG_NEURONA_DESPERTAR", 150),
        topk=_env_int("BIORAG_NEURONA_TOPK", 5),          # lo que ve quien busca sin decir cuánto verá
        topk_max=_env_int("BIORAG_NEURONA_TOPK_MAX", 10),  # tope de la vista (lo que ve el agente por el MCP)
        tope_nodo=_env_int("BIORAG_NEURONA_TOPE_POR_NODO", 4),
        pausa=_env_float("BIORAG_NEURONA_PAUSA_S", 3600.0),
        refresco=_env_float("BIORAG_NEURONA_REFRESCO_S", 30.0),
        tol_campeon=max(0, _env_int("BIORAG_NEURONA_TOL_CAMPEON", 1)),  # casos por categoría
    )


# ───────────────────────── capas de protección ─────────────────────────
# Cada una cubre una falla concreta de "una neurona viva dentro de BioRAG".

_hilo = threading.local()          # silencio por HILO: el DMN y el MCP buscan en paralelo
_CREAR_CANDADO = threading.Lock()


def _candado(self):
    """Un solo ciclo de aprendizaje a la vez por cerebro (sueño y consolidar pueden coincidir)."""
    c = self.__dict__.get("_neurona_candado")
    if c is None:
        with _CREAR_CANDADO:
            c = self.__dict__.setdefault("_neurona_candado", threading.Lock())
    return c


def _sano(p):
    """Pesos utilizables: todos finitos y acotados (un entrenamiento que diverge no entra)."""
    try:
        return p is not None and all(np.all(np.isfinite(v)) and float(np.max(np.abs(v))) < 1e3 for v in p.values())
    except Exception:
        return False


def _en_pausa(self, que):
    return time.time() < float(self.__dict__.get(f"_neurona_pausa_{que}", 0.0))


def _fallo(self, que, e):
    """Cortacircuitos: 3 fallas seguidas -> esa parte se pausa (el motor sigue como siempre)."""
    n = int(self.__dict__.get(f"_neurona_fallos_{que}", 0)) + 1
    self.__dict__[f"_neurona_fallos_{que}"] = n
    if n >= 3:
        self.__dict__[f"_neurona_pausa_{que}"] = time.time() + _cfg()["pausa"]
        self.__dict__[f"_neurona_fallos_{que}"] = 0
        logger.warning("neurona: %s falló 3 veces seguidas; se pausa %.0fs (%s)", que, _cfg()["pausa"], e)
    else:
        logger.warning("neurona: %s falló; el motor sigue igual (%s)", que, e)


def _bien(self, que):
    self.__dict__[f"_neurona_fallos_{que}"] = 0


def huella_motor(self):
    """Huella del COMPORTAMIENTO de la fórmula a mano (no de su código).

    Se pasan entradas fijas por `_calcular_score_hibrido` y por `rasgos` y se
    resume la salida. Si alguien cambia un peso, una constante o una variable
    de entorno del motor, la huella cambia y lo aprendido con el motor viejo
    deja de usarse (se vuelve a aprender desde los pesos a mano).
    """
    try:
        r = np.random.default_rng(12345)
        salida = [str(F_SIG), str(OCULTAS), str(VERSION)]
        for i in range(12):
            kw = dict(bm25_norm=r.random(), dim_score=r.random(), concepto_ratio=r.random(),
                      sinonimos_ratio=r.random(), score_latente=r.random(), score_cadena=r.random(),
                      asoc_count=int(r.integers(0, 30)), match_exacto=bool(i % 4 == 0),
                      grupo_score=r.random(), tematico_score=r.random(), jsd_score=r.random(),
                      jsd_weight=0.05 if i % 2 else 0.0, pred_score=r.random(), ppmi_score=r.random(),
                      hub_match=r.random(), ncd_score=r.random(), episodio_score=r.random(),
                      analogia_score=r.random(), campo_score=r.random(), peso_sinaptico=r.random())
            salida.append(f"{float(self._calcular_score_hibrido(**kw)):.6f}")
            salida.append(",".join(f"{x:.6f}" for x in rasgos(kw)))
        return hashlib.sha256("|".join(salida).encode()).hexdigest()[:16]
    except Exception:
        return "desconocida"


# ───────────────────────── rasgos y escala ─────────────────────────

def rasgos(kw):
    """Las 17 agujas que ve la neurona, desde los argumentos de la fórmula a mano."""
    g = kw.get
    bm25, conc = float(g("bm25_norm", 0.0) or 0.0), float(g("concepto_ratio", 0.0) or 0.0)
    lex = bm25 > .001 or conc > .001
    sin = float(g("sinonimos_ratio", 0.0) or 0.0)
    return (bm25, float(g("dim_score", 0.0) or 0.0), conc, sin,
            max(float(g("score_latente", 0.0) or 0.0), float(g("score_cadena", 0.0) or 0.0)),
            float(g("grupo_score", 0.0) or 0.0),
            float(g("tematico_score", 0.0) or 0.0) if lex else 0.0,
            min(1.0, float(g("asoc_count", 0) or 0) / 20.0),
            float(g("pred_score", 0.0) or 0.0), float(g("ppmi_score", 0.0) or 0.0),
            float(g("hub_match", 0.0) or 0.0), float(g("ncd_score", 0.0) or 0.0),
            float(g("episodio_score", 0.0) or 0.0), float(g("campo_score", 0.0) or 0.0),
            float(g("jsd_score", 0.0) or 0.0),
            1.0 if g("match_exacto") else 0.0, 1.0 if sin >= .95 else 0.0)


_EPS = 1e-4
_L1 = math.log((1 - _EPS) / _EPS)
_PEND = 1.0 / (_EPS * (1 - _EPS))


def g(s):
    """logit, prolongado en recta por encima de 1 (los matches exactos no se recortan)."""
    s = max(_EPS, float(s))
    if s < 1 - _EPS:
        return math.log(s / (1 - s))
    return _L1 + (s - (1 - _EPS)) * _PEND


def _correccion(p, X):
    return np.tanh(X @ p["W"].T + p["b"]) @ p["v"]


def _base(score):
    """Escala de la fórmula para la neurona: logit del score SERVIDO (acotado)."""
    return g(min(max(float(score), _EPS), 50.0))


def vista(pagina, rasgos_pool, origen, bonos, evidencia, con_peso, con_agente, no_literales=(), k=None):
    """Lo que ve la neurona: los primeros k de la página TAL COMO SE SIRVE.

    Una sola función para aprender y para servir (desfase 0 por construcción):
    el autoexamen guarda esta vista y `reordenar` corrige esta misma vista.
    Por fila: las 17 agujas de la fórmula + lo que pasó después de la fórmula
    (bono de convergencia, evidencia por campo, peso, origen) + el contexto de
    la búsqueda (¿el score incluye peso? ¿vino con sustantivos del agente?).
    k = lo que verá quien pidió la búsqueda (el MCP muestra `convergencia_limite`,
    10); sin dato, `topk` (5). Tope `topk_max`: costo fijo.
    Nunca lanza: si algo no cuadra devuelve None y nadie reordena.
    """
    try:
        cfg = _cfg()
        k = min(int(k or cfg["topk"]), cfg["topk_max"], len(pagina))
        if k < 2:
            return None
        bonos, evidencia, origen = bonos or {}, evidencia or {}, origen or {}
        filas, nombres = [], []
        for r in pagina[:k]:
            c = r[0]
            f = (rasgos_pool or {}).get(c)
            ev = evidencia.get(c) or {}
            o = (origen.get(c) or ("literal", 0.0))[0]
            filas.append(list(f[0] if f else [0.0] * len(F_FORMULA)) + [
                min(1.5, max(0.0, float(bonos.get(c, 0.0) or 0.0) / 0.085)),
                float(ev.get("concepto", 0.0) or 0.0), float(ev.get("sinonimos", 0.0) or 0.0),
                float(ev.get("sustantivos_clave", 0.0) or 0.0), float(ev.get("contenido", 0.0) or 0.0),
                min(1.0, max(0.0, float(r[2] or 0.0))), float(bool(con_peso)), float(bool(con_agente)),
                float(o == "lexico_aprendido"), float(o == "concept_hub"), float(o in no_literales),
                float(f is None)])
            nombres.append(c)
        X = np.array(filas, dtype=np.float32)
        base = np.array([_base(r[4]) for r in pagina[:k]], dtype=np.float32)
        if X.shape != (k, len(F_SIG)) or not (np.all(np.isfinite(X)) and np.all(np.isfinite(base))):
            return None
        return dict(nombres=nombres, X=X, base=base)
    except Exception:
        return None


MARGENES = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0)


def _margen_valido(m, tope=None):
    """Un margen negativo haría a la neurona MÁS atrevida que la fórmula: nunca se acepta."""
    try:
        m = float(m)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(m) or m < 0 or (tope is not None and m > tope):
        return None
    return m


def _margen_servir(est):
    forzado = _margen_valido(os.environ.get("BIORAG_NEURONA_MARGEN") or None)
    return forzado if forzado is not None else est.margen


def _prior(k, margen):
    """Ventaja por puesto de la fórmula: para subir un puesto hay que ganar por `margen`."""
    return margen * (k - np.arange(k))


def _es_guardia(concepto):
    return int(hashlib.sha256(concepto.encode("utf-8")).hexdigest()[:8], 16) % 5 == 0


# ───────────────────────── estado (persistido en la DB) ─────────────────────────

class _Estado:
    def __init__(self):
        self.campeon = None
        self.margen = 0.0        # "primero no dañar": ventaja mínima para moverle el puesto a la fórmula
        self.retador = self._nuevo(0)
        self.adam = None
        self.estudio, self.guardia = [], []
        self.stats = dict(version=VERSION, ciclos=0, preguntas=0, ascensos=0, retiros=0,
                          reinicios=0, sin_mejora=0, tranquila=False, nuevas_desde_tranquila=0,
                          descartes=0, purgados=0, ultimo={})
        self.huella = None
        self.leido_en = 0.0      # 'actualizado' de la fila que tenemos en RAM (varios procesos)
        self.mirado_en = 0.0     # última vez que se miró si otro proceso escribió

    @staticmethod
    def _nuevo(semilla):
        r = np.random.default_rng(semilla)
        return {"W": r.normal(0, .1, (OCULTAS, len(F_SIG))), "b": np.zeros(OCULTAS), "v": np.zeros(OCULTAS)}


def _tabla(self):
    self.cursor.execute("CREATE TABLE IF NOT EXISTS neurona_estado ("
                        "clave TEXT PRIMARY KEY, valor BLOB, actualizado REAL)")


def _cargar(self):
    est = _Estado()
    est.huella = huella_motor(self)
    est.mirado_en = time.time()
    try:
        filas = {c: (v, t) for c, v, t in self.cursor.execute(
            "SELECT clave, valor, actualizado FROM neurona_estado").fetchall()}
    except Exception:
        return est  # tabla aún no existe: DB nueva
    try:
        if "pesos" in filas:
            est.leido_en = float(filas["pesos"][1] or 0.0)
            d = json.loads(filas["pesos"][0])
            if d.get("version") != VERSION or d.get("huella") != est.huella:
                # El motor cambió (o es otra versión de la neurona): lo aprendido ya no aplica.
                logger.info("neurona: la fórmula del motor cambió; se vuelve a aprender desde los pesos a mano")
                est.stats["descartes"] = int(d.get("stats", {}).get("descartes", 0)) + 1
                return est
            est.stats.update(d.get("stats", {}))
            est.margen = _margen_valido(d.get("margen", 0.0), tope=MARGENES[-1])
            if est.margen is None:
                raise ValueError("margen inválido en el estado guardado")
            if d.get("campeon"):
                est.campeon = {k: np.array(v, dtype=float) for k, v in d["campeon"].items()}
            if d.get("retador"):
                est.retador = {k: np.array(v, dtype=float) for k, v in d["retador"].items()}
            if not _sano(est.campeon):
                est.campeon = None
            if not _sano(est.retador):
                est.retador = _Estado._nuevo(0)
        if "memoria" in filas:
            z = np.load(io.BytesIO(filas["memoria"][0]), allow_pickle=False)
            meta = json.loads(str(z["meta"]))
            for nombre, lista in (("estudio", est.estudio), ("guardia", est.guardia)):
                for i, m in enumerate(meta[nombre]):
                    X = z[f"{nombre}_X_{i}"].astype(np.float32)
                    b = z[f"{nombre}_b_{i}"].astype(np.float32)
                    if X.ndim != 2 or X.shape[1] != len(F_SIG) or len(b) != len(X) or not (0 <= m["y"] < len(b)):
                        continue  # caso dañado: se ignora, no se adivina
                    if not (np.all(np.isfinite(X)) and np.all(np.isfinite(b))):
                        continue
                    lista.append(dict(cat=m["cat"], nodo=m["nodo"], y=m["y"], q=m.get("q", ""),
                                      X=X, base=b))
    except Exception as e:
        logger.warning("neurona: estado ilegible, se arranca de los pesos a mano (%s)", e)
        limpio = _Estado()
        limpio.huella, limpio.leido_en, limpio.mirado_en = est.huella, est.leido_en, est.mirado_en
        return limpio
    return est


def _guardar(self, est):
    try:
        _tabla(self)
        pesos = json.dumps(dict(
            version=VERSION, huella=est.huella, stats=est.stats, margen=est.margen,
            campeon={k: v.tolist() for k, v in est.campeon.items()} if est.campeon else None,
            retador={k: v.tolist() for k, v in est.retador.items()}))
        arr, meta = {}, {"estudio": [], "guardia": []}
        for nombre, lista in (("estudio", est.estudio), ("guardia", est.guardia)):
            for i, c in enumerate(lista):
                arr[f"{nombre}_X_{i}"] = c["X"].astype(np.float16)
                arr[f"{nombre}_b_{i}"] = c["base"].astype(np.float32)
                meta[nombre].append(dict(cat=c["cat"], nodo=c["nodo"], y=int(c["y"]), q=c.get("q", "")))
        buf = io.BytesIO()
        np.savez_compressed(buf, meta=np.array(json.dumps(meta)), **arr)
        ahora = time.time()
        self.cursor.executemany(
            "INSERT OR REPLACE INTO neurona_estado (clave, valor, actualizado) VALUES (?, ?, ?)",
            [("pesos", pesos, ahora), ("memoria", buf.getvalue(), ahora)])
        self.conn.commit()
        est.leido_en = ahora
        return True
    except Exception as e:
        try:
            self.conn.rollback()
        except Exception:
            pass
        logger.warning("neurona: no se pudo guardar el estado (%s)", e)
        return False


def estado(self):
    est = self.__dict__.get("_neurona_estado")
    if est is None:
        est = _cargar(self)
        self._neurona_estado = est
    return est


def _refrescar(self, forzar=False):
    """Varios procesos sobre la misma DB (MCP + CLI): si otro escribió después, se recarga.

    Una lectura por clave primaria cada `refresco` segundos (o forzada antes de aprender).
    """
    est = estado(self)
    ahora = time.time()
    if not forzar and ahora - est.mirado_en < _cfg()["refresco"]:
        return est
    est.mirado_en = ahora
    try:
        fila = self.cursor.execute("SELECT actualizado FROM neurona_estado WHERE clave = 'pesos'").fetchone()
    except Exception:
        return est
    if fila and float(fila[0] or 0.0) > est.leido_en + 1e-6:
        est = _cargar(self)
        self._neurona_estado = est
    return est


def olvidar(self):
    """Vuelve a los pesos a mano y borra lo aprendido (para auditoría / pruebas)."""
    try:
        _tabla(self)
        self.cursor.execute("DELETE FROM neurona_estado")
        self.conn.commit()
    except Exception:
        pass
    est = _Estado()
    est.huella = huella_motor(self)
    self._neurona_estado = est


# ───────────────────────── servir: reordenar el top-5 ─────────────────────────

def _norm_nombre(t):
    return " ".join(str(t or "").lower().replace("_", " ").split())


def _es_su_nombre(frase, concepto):
    """¿La consulta ES el nombre del recuerdo? ("caso conflicto" == "caso_conflicto")."""
    q = _norm_nombre(frase)
    return bool(q) and q == _norm_nombre(concepto)


def silencio(self):
    """¿Esta búsqueda es de práctica? Solo en el HILO que está practicando con ESTE cerebro."""
    return getattr(_hilo, "silencio_de", None) is self


def entregar_vista(self, v):
    """search.py entrega aquí la vista servida (solo se guarda en la búsqueda de práctica)."""
    if silencio(self):
        _hilo.vista = v


def necesita_rasgos(self):
    """¿Vale la pena anotar las agujas de cada candidato en esta búsqueda?"""
    if not activa():
        return False
    if silencio(self):
        return True
    if _en_pausa(self, "reordenar"):
        return False
    try:
        return _refrescar(self).campeon is not None
    except Exception:
        return False


def reordenar(self, frase, pagina, v):
    """Reordena SOLO los primeros k de la página con el campeón, sobre la MISMA vista
    con la que aprendió. Nunca lanza."""
    try:
        if not activa() or silencio(self) or v is None or len(pagina) < 2 or _en_pausa(self, "reordenar"):
            return pagina
        est = estado(self)
        if est.campeon is None:
            return pagina
        k = len(v["nombres"])
        top = pagina[:k]
        if k < 2 or [r[0] for r in top] != v["nombres"]:
            return pagina  # la vista no corresponde a esta página: no se toca nada
        corr = _correccion(est.campeon, v["X"].astype(float))
        if not np.all(np.isfinite(corr)):
            return pagina
        claves = v["base"].astype(float) + corr + _prior(k, _margen_servir(est))
        orden = sorted(range(k), key=lambda i: (-claves[i], i))
        if _es_su_nombre(frase, top[0][0]):
            orden = [0] + [i for i in orden if i != 0]  # regla de identidad
        if orden == list(range(k)):
            return pagina
        scores = sorted((r[4] for r in top), reverse=True)
        nuevo = [tuple(top[i][:4]) + (scores[j],) + tuple(top[i][5:]) for j, i in enumerate(orden)]
        # Invariante: mismos nodos, mismos números. Si no se cumple, no se toca nada.
        if sorted(r[0] for r in nuevo) != sorted(r[0] for r in top) or \
                sorted(r[4] for r in nuevo) != sorted(r[4] for r in top):
            return pagina
        _permutar_mapas(self, [r[0] for r in top], [top[i][0] for i in orden])
        _bien(self, "reordenar")
        return nuevo + list(pagina[k:])
    except Exception as e:
        _fallo(self, "reordenar", e)
        return pagina


def _permutar_mapas(self, antes, despues):
    """Los consumidores (MCP: gate de ráfaga/certeza, score_base que ve el agente) leen
    `last_score_base_map` / `last_score_bonus_map` por concepto. Se permutan igual que los
    scores: cada POSICIÓN conserva exactamente sus números; solo cambia qué recuerdo la ocupa."""
    for nombre in ("last_score_base_map", "last_score_bonus_map"):
        mapa = self.__dict__.get(nombre)
        if not isinstance(mapa, dict):
            continue
        valores = [mapa.get(c, _FALTA) for c in antes]
        nuevo = dict(mapa)
        for c, v in zip(despues, valores):
            if v is _FALTA:
                nuevo.pop(c, None)
            else:
                nuevo[c] = v
        self.__dict__[nombre] = nuevo


_FALTA = object()


# ───────────────────────── aprender: autoexamen silencioso ─────────────────────────

@contextmanager
def _en_silencio(self):
    """Búsqueda de práctica: sin log, sin accesos ACT-R, sin DMN, sin pisar last_*.

    El silencio vale solo en este hilo. Al salir se restauran los last_* que la
    práctica cambió, pero SOLO si siguen teniendo el valor que dejó la práctica
    (si otro hilo los escribió mientras tanto, se respeta lo del otro hilo).
    """
    antes = {k: v for k, v in self.__dict__.items() if k.startswith("last_")}
    _hilo.silencio_de, _hilo.rasgos, _hilo.vista = self, None, None
    try:
        yield
    finally:
        _hilo.silencio_de = None
        for k, v in list(self.__dict__.items()):
            if not k.startswith("last_") or antes.get(k, _FALTA) is v:
                continue
            viejo = antes.get(k, _FALTA)
            if viejo is _FALTA:
                self.__dict__.pop(k, None)
            else:
                self.__dict__[k] = viejo


def _preguntar(self, concepto, consulta, cat, modo="crudo", limite_agente=10):
    """Una pregunta de práctica, respondida en silencio por el MISMO camino que en uso.

    modo "agente": como llega por el MCP `recordar` (pool 3x, convergencia sobre el
    top que ve el agente, peso sináptico, sustantivos_clave que extraería un agente
    de la consulta, sin mirar la respuesta). modo "crudo": el motor solo, como la QA.
    El caso es la vista servida: si la respuesta no está en el top-k, no hay nada
    que reordenar y no se guarda.
    """
    if modo == "agente":
        from core.memory.neurona_examen import sustantivos_de
        kw = dict(limite=3 * limite_agente, convergencia_limite=limite_agente,
                  sustantivos_clave_boost=sustantivos_de(consulta) or None)
    else:
        kw = dict(limite=5, ignore_peso_sinaptico=True)
    with _en_silencio(self):
        self.buscar_por_frase(consulta, profundidad="activos", **kw)
        v = getattr(_hilo, "vista", None)
        _hilo.vista = None
    if v is None or concepto not in v["nombres"]:
        return None
    return dict(cat=f"{cat}@{modo}", nodo=concepto, q=f"{modo}:{consulta}", y=v["nombres"].index(concepto),
                X=v["X"].astype(np.float32), base=v["base"].astype(np.float32))


def _nodos_a_examinar(self, conceptos, n, rng, prefiere=None):
    """Qué recuerdos examinar en este ciclo (como mucho `n`, costo fijo).

    Primero los recién consolidados. Si sobran lugares, recuerdos activos al azar;
    `prefiere` (True = de guardia, False = de estudio, None = cualquiera) pone primero
    los del grupo al que más le faltan preguntas: el que repasa lo que menos tiene.
    Nunca más de 4·n consultas a la DB, sin importar su tamaño.
    """
    elegidos = [c for c in dict.fromkeys(c.lower().strip() for c in conceptos if c)]
    rng.shuffle(elegidos)
    elegidos = elegidos[:n]
    try:
        tope = self.cursor.execute("SELECT MAX(rowid) FROM largo_plazo").fetchone()[0] or 0
        primero, despues, intentos = [], [], 0
        while len(elegidos) + len(primero) < n and tope and intentos < 4 * n:
            intentos += 1
            fila = self.cursor.execute(
                "SELECT concepto FROM largo_plazo WHERE rowid >= ? AND estado = 'activo' LIMIT 1",
                (rng.randint(1, tope),)).fetchone()
            if not fila or fila[0] in elegidos or fila[0] in primero or fila[0] in despues:
                continue
            if prefiere is None or _es_guardia(fila[0]) == prefiere:
                primero.append(fila[0])
            else:
                despues.append(fila[0])
        elegidos += primero
        elegidos += despues[:max(0, n - len(elegidos))]
    except Exception:
        pass
    return elegidos


def _le_falta(est, cfg):
    """¿A qué grupo del examen le falta más para su mínimo? True = guardia, False = estudio,
    None = a ninguno (o a los dos por igual): entonces se elige al azar, sin sesgo."""
    fg = max(0.0, 1.0 - len(est.guardia) / max(1, cfg["min_guardia"]))
    fe = max(0.0, 1.0 - len(est.estudio) / max(1, cfg["min_estudio"]))
    if fg == fe:
        return None
    return fg > fe


def _plano(casos):
    X = np.vstack([c["X"] for c in casos]).astype(float)
    base = np.concatenate([c["base"] for c in casos]).astype(float)
    tam = np.array([len(c["X"]) for c in casos])
    off = np.concatenate([[0], np.cumsum(tam)[:-1]])
    seg = np.repeat(np.arange(len(casos)), tam)
    y = off + np.array([c["y"] for c in casos])
    return X, base, off, seg, y


def _preparar(p, casos, topk):
    """Lo caro (top-k de la fórmula y corrección de la red) se calcula una vez por pesos."""
    prep = []
    for c in casos:
        top = np.arange(min(topk, len(c["base"])))  # los casos YA vienen en el orden servido (k = lo que se vio)
        corr = _correccion(p, c["X"][top].astype(float)) if p is not None else None
        prep.append((top, c["base"][top].astype(float), corr, c["y"]))
    return prep


def _rangos_desde(prep, margen=0.0):
    out = np.zeros(len(prep), dtype=int)
    for i, (top, base, corr, y) in enumerate(prep):
        if corr is not None:
            top = top[np.argsort(-(base + corr + _prior(len(top), margen)), kind="stable")]
        donde = np.nonzero(top == y)[0]
        out[i] = int(donde[0]) + 1 if len(donde) else 0
    return out


def _rangos(p, casos, topk, margen=0.0):
    """Puesto (1..k, 0 = fuera del top-k) de la respuesta, sirviendo como en producción:
    la fórmula elige el top-k y la neurona solo lo reordena (con su margen)."""
    return _rangos_desde(_preparar(p, casos, topk), margen)


def _calibrar(p, todos, n_est, r_mano, piso, g_min, t_min, topk, piso_campeon=None, tol=1, motivo=None):
    """PRIMERO NO DAÑAR: el menor margen con el que estos pesos
      - no pierden NINGÚN caso de la guardia que la fórmula acertaba,
      - en todo el examen pierden menos del 5 % de lo que ganan,
      - no bajan ninguna categoría (aciertos #1 ni MRR),
      - si hay campeón (`piso_campeon`), no quedan por debajo de él en ninguna
        categoría por más de `tol` casos,
      - y alcanzan los mínimos pedidos de guardia y total.
    Devuelve (margen, rangos) o (None, None) si ningún margen lo logra. Si se pasa
    `motivo` (dict), anota motivo["campeon"] = True cuando algún margen cumplía todo
    menos el piso contra el campeón (para saber cuántas veces la regla actuó)."""
    a_mano = r_mano == 1
    t5_mano = (r_mano >= 1) & (r_mano <= 5)
    prep = _preparar(p, todos, topk)
    for m in MARGENES:
        r = _rangos_desde(prep, m)
        a = r == 1
        pierde, gana = a_mano & ~a, ~a_mano & a
        if pierde[n_est:].any() or pierde.sum() > 0.05 * gana.sum():
            continue
        # con vistas de más de 5 (MCP) la neurona podría sacar a alguien del top-5:
        # el R@5 tampoco puede bajar (ningún caso de guardia sale; en total, a lo sumo
        # el 5 % de los que entran)
        t5 = (r >= 1) & (r <= 5)
        sale5, entra5 = t5_mano & ~t5, ~t5_mano & t5
        if sale5[n_est:].any() or sale5.sum() > 0.05 * entra5.sum():
            continue
        pc = _por_cat(r, todos)
        if not _cumple_piso(pc, piso):
            continue
        if int(a[n_est:].sum()) < g_min or int(a.sum()) < t_min:
            continue
        if piso_campeon is not None and not _cumple_campeon(pc, piso_campeon, tol):
            if motivo is not None:
                motivo["campeon"] = True
            continue
        return m, r
    return None, None


def _por_cat(rangos, casos):
    """Por categoría: (aciertos #1, suma de 1/puesto en el top-5, aciertos en el top-5).
    Las mismas tres métricas de la QA (R@1, MRR, R@5): el piso exige no bajar en ninguna."""
    d = {}
    for r, c in zip(rangos, casos):
        a1, rr, a5 = d.get(c["cat"], (0, 0.0, 0))
        en5 = 1 <= r <= 5
        d[c["cat"]] = (a1 + int(r == 1), rr + (1.0 / r if en5 else 0.0), a5 + int(en5))
    return d


def _cumple_campeon(pc, campeon, tol):
    """Por categoría, el retador no queda debajo del campeón saliente por más de `tol`
    casos en aciertos #1, en suma de 1/puesto (MRR) ni en aciertos del top-5."""
    cero = (0, 0.0, 0)
    return all(pc.get(k, cero)[i] >= v[i] - tol - 1e-9 for k, v in campeon.items() for i in range(len(v)))


def _r1(p, casos, topk):
    return _rangos(p, casos, topk) == 1


def _cumple_piso(pc, piso):
    cero = (0, 0.0, 0)
    return all(pc.get(k, cero)[i] >= v[i] - 1e-9 for k, v in piso.items() for i in range(len(v)))


def _paso(est, P, lr, l2):
    X, base, off, seg, y = P
    p = est.retador
    H = np.tanh(X @ p["W"].T + p["b"])
    s = base + H @ p["v"]
    e = np.exp(s - np.maximum.reduceat(s, off)[seg])
    pr = e / np.add.reduceat(e, off)[seg]
    d = pr.copy()
    d[y] -= 1.0
    n = len(off)
    dH = np.outer(d, p["v"]) * (1 - H ** 2)
    grads = {"v": H.T @ d, "W": dH.T @ X, "b": dH.sum(0)}
    if est.adam is None:
        est.adam = {"t": 0, "m": {k: np.zeros_like(v) for k, v in p.items()},
                    "s": {k: np.zeros_like(v) for k, v in p.items()}}
    a = est.adam
    a["t"] += 1
    for k in p:
        gk = grads[k] / n + l2 * p[k]
        a["m"][k] = .9 * a["m"][k] + .1 * gk
        a["s"][k] = .999 * a["s"][k] + .001 * gk ** 2
        p[k] = p[k] - lr * (a["m"][k] / (1 - .9 ** a["t"])) / (np.sqrt(a["s"][k] / (1 - .999 ** a["t"])) + 1e-8)


def _copiar(p):
    return {k: v.copy() for k, v in p.items()} if p is not None else None


def _evaluar_y_decidir(est, cfg):
    """Entrena al retador y decide si asciende. Devuelve un resumen del ciclo."""
    todos = est.estudio + est.guardia
    res = {"estudio": len(est.estudio), "guardia": len(est.guardia)}
    if len(est.estudio) < cfg["min_estudio"] or len(est.guardia) < cfg["min_guardia"]:
        res["fase"] = "juntando examen"
        return res
    r_mano = _rangos(None, todos, cfg["topk_max"])
    a_mano = r_mano == 1
    piso = _por_cat(r_mano, todos)
    ng, n_est = len(est.guardia), len(est.estudio)
    g_mano, t_mano = int(a_mano[n_est:].sum()), int(a_mano.sum())

    # 1) ¿el campeón sigue sin dañar con la DB de hoy? Se recalibra su margen; si
    #    ningún margen lo deja sin dañar, se retira y vuelven los pesos a mano.
    campeon_ref = a_mano
    piso_campeon = None                    # por categoría, lo que el campeón saliente ya logra
    if est.campeon is not None:
        # debe seguir GANANDO a la fórmula (si solo empata, sobra: se retira)
        m, r_c = _calibrar(est.campeon, todos, n_est, r_mano, piso, g_mano, t_mano + 1, cfg["topk_max"])
        if m is None:
            est.campeon, est.margen = None, 0.0
            est.stats["retiros"] += 1
            est.stats["tranquila"] = False
            est.stats["sin_mejora"] = 0
            res["retiro"] = True
        else:
            est.margen = m
            campeon_ref = r_c == 1
            piso_campeon = _por_cat(r_c, todos)
    g_ref, t_ref = int(campeon_ref[n_est:].sum()), int(campeon_ref.sum())
    res["margen"] = est.margen

    if est.stats["tranquila"]:
        if est.stats["nuevas_desde_tranquila"] < cfg["despertar"]:
            res["fase"] = "tranquila"
            res.update(guardia_campeon=g_ref / ng, guardia_mano=g_mano / ng)
            return res
        est.stats["tranquila"] = False
        est.stats["sin_mejora"] = 0

    # 2) el retador estudia (solo el estudio; la guardia nunca)
    P = _plano(est.estudio)
    respaldo = _copiar(est.retador)
    for _ in range(cfg["pasos"]):
        _paso(est, P, cfg["lr"], cfg["l2"])
    if not _sano(est.retador):
        # el entrenamiento divergió (NaN/inf): se descarta este tramo, no entra nada roto
        est.retador = respaldo if _sano(respaldo) else _Estado._nuevo(est.stats["reinicios"] + 1)
        est.adam = None
        est.stats["reinicios"] += 1
        res.update(fase="estudiando", divergio=True)
        return res
    a_r = _rangos(est.retador, todos, cfg["topk_max"]) == 1     # sin margen: diagnóstico de memorización
    res.update(guardia_mano=g_mano / ng, guardia_retador=int(a_r[n_est:].sum()) / ng, guardia_campeon=g_ref / ng)
    # anti-memorización: estudia cada vez mejor pero la guardia no lo sigue. Si la guardia
    # lo delata, NO asciende aunque un margen grande lo deje "sin dañar": sus ganancias
    # serían de memoria, no de generalizar (hueco hallado en el experimento 07).
    brecha = a_r[:n_est].mean() - a_r[n_est:].mean()
    brecha0 = a_mano[:n_est].mean() - a_mano[n_est:].mean()
    memoriza = brecha - brecha0 > .05
    m, r_r = (None, None)
    if _sano(est.retador) and not memoriza:
        motivo = {}
        m, r_r = _calibrar(est.retador, todos, n_est, r_mano, piso, g_ref, t_ref + 1, cfg["topk_max"],
                           piso_campeon, cfg["tol_campeon"], motivo)
        if m is None and motivo.get("campeon"):
            res["veto_campeon"] = True     # ganaba en total, pero cedía una categoría al campeón

    if m is not None:
        est.campeon, est.margen = _copiar(est.retador), m
        est.stats["ascensos"] += 1
        est.stats["sin_mejora"] = 0
        res.update(fase="ascenso", margen=m, guardia_campeon=int((r_r == 1)[n_est:].sum()) / ng)
    else:
        est.stats["sin_mejora"] += 1
        res["fase"] = "estudiando"
        if memoriza:
            est.retador = _copiar(est.campeon) if est.campeon is not None else _Estado._nuevo(est.stats["reinicios"] + 1)
            est.adam = None
            est.stats["reinicios"] += 1
            res["reinicio"] = True
        if est.stats["sin_mejora"] >= cfg["paciencia"]:
            est.stats["tranquila"] = True
            est.stats["nuevas_desde_tranquila"] = 0
            res["fase"] = "tranquila (techo)"
    return res


def _meter(lista, caso, maximo, rng, tope_nodo):
    """Memoria de examen de tamaño fijo, siempre fresca y sin que un recuerdo la acapare.

    - misma pregunta del mismo recuerdo: se reemplaza (no se duplica);
    - un recuerdo guardado 100 veces no puede ocupar más de `tope_nodo` lugares
      (si no, la neurona memorizaría ese recuerdo);
    - llena: reemplazo al azar.
    """
    mios = [i for i, c in enumerate(lista) if c["nodo"] == caso["nodo"]]
    for i in mios:
        if lista[i].get("q") == caso.get("q"):
            lista[i] = caso
            return
    if len(mios) >= tope_nodo:
        lista[rng.choice(mios)] = caso
    elif len(lista) < maximo:
        lista.append(caso)
    else:
        lista[rng.randrange(maximo)] = caso


def _purgar_olvidados(self, est, rng, n=20):
    """Revisa unos pocos casos al azar (costo fijo): si su recuerdo ya no está activo
    (borrado, fusionado o dormido) el caso sale del examen."""
    quitados = 0
    for lista in (est.estudio, est.guardia):
        for i in sorted(rng.sample(range(len(lista)), min(n, len(lista))), reverse=True):
            fila = self.cursor.execute(
                "SELECT 1 FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (lista[i]["nodo"],)).fetchone()
            if not fila:
                lista.pop(i)
                quitados += 1
    est.stats["purgados"] = est.stats.get("purgados", 0) + quitados
    return quitados


def practicar(self, conceptos=(), nodos=None, presupuesto_s=None):
    """Un ciclo de aprendizaje en vivo. Costo acotado. Nunca lanza.

    `conceptos`: los recuerdos recién consolidados (se examinan primero).
    Devuelve un dict con lo que pasó (para trazas y pruebas).
    """
    if not activa() or silencio(self):
        return {"fase": "apagada"}
    if _en_pausa(self, "practicar"):
        return {"fase": "en pausa por fallas"}
    candado = _candado(self)
    if not candado.acquire(blocking=False):
        return {"fase": "ocupada"}  # otro hilo ya está practicando: no se espera, no se bloquea
    try:
        return _practicar(self, conceptos, nodos, presupuesto_s)
    finally:
        candado.release()


def _practicar(self, conceptos, nodos, presupuesto_s):
    t0 = time.time()
    try:
        cfg = _cfg()
        nodos = cfg["nodos"] if nodos is None else nodos
        presupuesto = cfg["presupuesto"] if presupuesto_s is None else presupuesto_s
        est = _refrescar(self, forzar=True)
        if est.stats.get("tranquila"):
            nodos = max(1, nodos // 2)  # en el techo solo vigila: mitad de costo
        rng = random.Random(est.stats["ciclos"] * 7919 + 17)
        _purgar_olvidados(self, est, rng)
        from core.memory.neurona_examen import preguntas
        # Preguntas A LO ANCHO: primero la 1ª de cada recuerdo, luego la 2ª de cada uno...
        # Si el presupuesto corta (DB grande, búsquedas lentas) las preguntas quedan
        # repartidas entre muchos recuerdos distintos y no amontonadas en uno o dos:
        # así la neurona conoce más recuerdos y no se acostumbra a pocos. En una DB
        # chica (rápida) alcanza para todas igual.
        listas = []
        for concepto in _nodos_a_examinar(self, conceptos, nodos, rng, _le_falta(est, cfg)):
            fila = self.cursor.execute(
                "SELECT contenido, COALESCE(sinonimos, '') FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
                (concepto,)).fetchone()
            if not fila:
                continue
            qs = preguntas(concepto, fila[0], fila[1])
            rng.shuffle(qs)
            listas.append((concepto, qs[:cfg["preguntas"]]))
        orden = [(c, qs[r]) for r in range(max(0, cfg["preguntas"])) for c, qs in listas if r < len(qs)]
        nuevas, lenta, turno = 0, 0.0, 0
        for concepto, (cat, q) in orden:
            # no empezar una pregunta que no cabe en el presupuesto (estimación: la más lenta hasta ahora)
            if time.time() - t0 + lenta > presupuesto:
                break
            # aprende los dos caminos por igual: se alterna en todo el ciclo
            modo = MODOS[(turno + est.stats["ciclos"]) % len(MODOS)]
            turno += 1
            tq = time.time()
            caso = _preguntar(self, concepto, q, cat, modo, cfg["limite_agente"])
            lenta = max(lenta, time.time() - tq)
            if caso is None:
                continue
            if _es_guardia(concepto):
                _meter(est.guardia, caso, cfg["max_guardia"], rng, cfg["tope_nodo"])
            else:
                _meter(est.estudio, caso, cfg["max_estudio"], rng, cfg["tope_nodo"])
            nuevas += 1
        est.stats["ciclos"] += 1
        est.stats["preguntas"] += nuevas
        est.stats["nuevas_desde_tranquila"] += nuevas
        res = _evaluar_y_decidir(est, cfg)
        res.update(nuevas=nuevas, campeon=est.campeon is not None, ms=round((time.time() - t0) * 1000))
        est.stats["ultimo"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()}
        res["guardado"] = _guardar(self, est)
        _bien(self, "practicar")
        return res
    except Exception as e:
        _fallo(self, "practicar", e)
        return {"fase": "error", "error": str(e)}


def resumen(self):
    """Estado legible de la neurona (para herramientas de diagnóstico)."""
    est = estado(self)
    return dict(activa=activa(), campeon=est.campeon is not None, margen=est.margen,
                estudio=len(est.estudio), guardia=len(est.guardia), **{k: v for k, v in est.stats.items()})
