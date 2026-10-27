"""Neurona de Puentes (v1): ¿cuánto me creo este puente EN ESTA consulta?

Misma disciplina que `core/memory/neurona.py`, mismo molde, distinto trabajo.

QUÉ ES
    Un adaptador hexagonal que se mete entre el Concept Hub y el score. Recibe
    lo que el hub ya sabe de un puente (cobertura IDF, ángulos, longitud,
    margen sobre el segundo hub) y devuelve un MULTIPLICADOR de confianza
    acotado a [FLOOR, TECHO] = [0.5, 1.0].

    No decide si el puente es evidencia — eso lo sigue decidiendo el umbral,
    que está calibrado y es auditable. Decide CUÁNTO pesa un puente que ya
    pasó. Son dos preguntas distintas y este módulo no las mezcla.

DOS ETAPAS, A PROPÓSITO
    1. Compuerta (determinista, calibrada): `cobertura_idf >= umbral`.
       Responde "¿esto es evidencia de que la consulta habla de este nodo?".
       Se mide, se audita, y no se toca sin volver a medir.
    2. Confianza (aprendida): este módulo. Responde "de los que pasaron,
       ¿cuál es ruido?".

    Por qué separadas: si la neurona pudiera cerrar la compuerta, un
    multiplicador de 0.5 sobre una cobertura de 1.0 daría 0.50 y mataría los
    cinco casos oficiales del hub. La neurona ordena y atenúa; la compuerta
    sigue siendo la que deja entrar. Así ningún aprendizaje puede apagar el
    mecanismo por accidente.

CONTRATO (lo que no puede cambiar sin romper la arquitectura)
    Entrada : 15 números en [0,1] (`rasgos_puente`). Nada de texto, nada de
              embeddings: solo estadística que el hub ya calculó. Coste O(1),
              no depende del tamaño del cerebro.
    Salida  : float en [0.5, 1.0]. 1.0 = "igual que hoy".
    Fallback: ante CUALQUIER duda (módulo apagado, pesos corruptos, excepción,
              tabla ilegible) devuelve 1.0 y el motor sigue con la fórmula a
              mano. Nunca lanza, nunca rompe una búsqueda.
    Neutro  : con los pesos a cero, la salida es exactamente 1.0. La neurona
              recién nacida es indistinguishable de no tenerla. Igual que
              `c(x)=0` en la neurona de ranking.

CÓMO APRENDE (sin etiquetas humanas)
    El maestro es el motor, no una persona. Para cada consulta con nodo
    conocido (la suite QA), se miran los puentes que dispararon:
      y = 1  si el nodo que el hub promociona es el correcto
      y = 0  si no lo es
    El puente se examina con la respuesta a la vista, igual que el autoexamen
    de la neurona de ranking. Sin anotar a mano, sin llamar a nadie.

PISO Y TECHO
    - Piso: la salida nunca baja de 0.5. Un puente no se puede apagar desde
      aquí; se puede despriorizar. La compuerta y el recall quedan intactos.
    - Techo: 1.0. La neurona no puede inventar confianza que la calibración no
      dio. Después de medir que el hub sobre-confiado costaba 0.68 pp de R@1,
      dejar que una neurona suba pesos por encima de lo calibrado sería
      reintroducir el mismo error con otro nombre.

PIEZAS QUE FALTAN (no las inventa este archivo)
    - Etiquetas: `scripts/entrenar_neurona_puentes.py` (a construir).
    - Guardia: 20 % de los nodos, elegidos por hash, no se entrenan nunca.
    - Medición: la suite QA con la neurona ON/OFF. Si no mejora, se apaga y
      el sistema queda como está.
"""
import json
import logging
import math
import os
import time

import numpy as np

logger = logging.getLogger("BioRAG.NeuronaPuentes")

VERSION = 1

# Dimensiones del contrato. Si cambia este número, el estado guardado se
# descarta y se vuelve a entrenar (misma regla que la neurona de ranking).
N_ENTRADAS = 15
N_OCULTAS = 4

ANGULOS = ("sinonimo", "problema", "solucion", "situacion", "ingenuo")

_TABLA = "neurona_puentes_estado"


# ───────────────────────── configuración ─────────────────────────

def _env_float(nombre, defecto):
    try:
        return float(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return float(defecto)


def _env_int(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return int(defecto)


def activa():
    """Interruptor. Apagada, el hub se comporta exactamente como sin neurona."""
    return os.environ.get("BIORAG_NEURONA_PUENTES", "1") != "0"


def _cfg():
    suelo = _env_float("BIORAG_PUENTES_SUELO", 0.5)
    techo = _env_float("BIORAG_PUENTES_TECHO", 1.0)
    if not (0.0 <= suelo < techo <= 1.0):
        suelo, techo = 0.5, 1.0
    return dict(
        suelo=suelo,
        techo=techo,
        pasos=_env_int("BIORAG_PUENTES_PASOS", 200),
        lr=_env_float("BIORAG_PUENTES_LR", 0.05),
        l2=_env_float("BIORAG_PUENTES_L2", 1e-3),
        pausa=_env_float("BIORAG_PUENTES_PAUSA_S", 3600.0),
    )


# ───────────────────────── rasgos (entrada) ─────────────────────────

def rasgos_puente(cobertura, idf_medio, idf_total, n_query, n_puente, n_matched,
                  fuera_vocab, angulo, margen, peso):
    """Los 15 números del contrato. Todo en [0,1], todo ya calculado por el hub.

    No hay texto aquí: el hub ya tokenizó, ya midió, ya sabe. Esta función solo
    normaliza para que la neurona vea siempre la misma escala, sin importar si
    la consulta tiene 2 palabras o el cerebro tiene 5 000 puentes.

    Args:
        cobertura:   fracción del IDF de la consulta que explica el puente (0..1).
        idf_medio:   IDF medio de las raíces compartidas, normalizado por idf_max.
        idf_total:   suma de IDF compartida / (n_query * idf_max). Penaliza
                     consultas largas con mucha cola rara.
        n_query:     raíces de contenido en la consulta.
        n_puente:    raíces de contenido en el puente.
        n_matched:   raíces compartidas.
        fuera_vocab: fracción de raíces de la consulta que NO están en el
                     vocabulario de puentes (lo más específico que el puente
                     no puede explicar).
        angulo:      uno de ANGULOS, o None.
        margen:      ventaja de confianza sobre el segundo hub (0..1).
        peso:        peso almacenado del puente.
    """
    def _f(x):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if not math.isfinite(x) else min(1.0, max(0.0, x))

    nq = max(1, int(n_query or 1))
    np_ = max(1, int(n_puente or 1))
    nm = max(0, min(int(n_matched or 0), nq))

    ang = [_f(1.0 if (angulo or "") == a else 0.0) for a in ANGULOS]

    return (
        _f(cobertura),                                   # 1  señal principal
        _f(idf_medio),                                   # 2  especificidad media
        _f(idf_total),                                   # 3  masa informativa
        _f(nm / nq),                                     # 4  cobertura de raíces
        _f(nm / np_),                                    # 5  precisión sobre el puente
        _f(nq / 12.0),                                   # 6  largo de la consulta
        _f(np_ / 8.0),                                   # 7  largo del puente
        _f(fuera_vocab),                                 # 8  lo que el puente no cubre
        *ang,                                            # 9-13 ángulo
        _f(margen),                                      # 14 desempate entre hubs
        _f(peso),                                        # 15 peso almacenado
    )


def rasgos_desde_cero():
    """Vector neutro: lo que ve la neurona cuando no hay nada que medir."""
    return (0.0,) * N_ENTRADAS


# ───────────────────────── pesos ─────────────────────────

# W nace pequeño y aleatorio, pero DETERMINISTA (semilla fija): rompe la
# simetría para que el entrenamiento pueda moverse. Si W naciera en cero, el
# gradiente de W sería siempre cero y la neurona no aprendería jamás.
# Lo que garantiza la neutralidad no es W: es `v = 0` (ver `_nuevo_params`).
_W_INICIAL = np.random.default_rng(0).normal(0.0, 0.1, (N_OCULTAS, N_ENTRADAS))


def _nuevo_params():
    """Pesos neutros: `v = 0` -> la corrección es exactamente 0 -> salida 1.0.

    La neutralidad se cumple por construcción, no por casualidad: con v=0 el
    producto `tanh(W·x+b)·v` es 0 para CUALQUIER x, aunque W sea aleatoria.
    """
    return dict(
        W=_W_INICIAL.copy(),
        b=np.zeros(N_OCULTAS),
        v=np.zeros(N_OCULTAS),
    )


def es_neutra(p):
    """¿La neurona es indistinguible de no tenerla? Solo depende de `v`."""
    try:
        return bool(np.all(np.asarray(p["v"]) == 0.0))
    except Exception:
        return True


def _sano(p):
    """Pesos utilizables: todos finitos y acotados. Un entrenamiento que
    divergió no entra. Misma regla que la neurona de ranking."""
    try:
        return (p is not None
                and set(p) == {"W", "b", "v"}
                and p["W"].shape == (N_OCULTAS, N_ENTRADAS)
                and p["b"].shape == (N_OCULTAS,)
                and p["v"].shape == (N_OCULTAS,)
                and all(np.all(np.isfinite(v)) and float(np.max(np.abs(v))) < 1e3
                        for v in p.values()))
    except Exception:
        return False


def _tabla(conn):
    conn.execute(f"CREATE TABLE IF NOT EXISTS {_TABLA} ("
                 "clave TEXT PRIMARY KEY, valor BLOB, actualizado REAL)")


def cargar(conn):
    """Pesos guardados, o los neutros. Nunca lanza."""
    try:
        fila = conn.execute(
            f"SELECT valor FROM {_TABLA} WHERE clave = 'pesos'").fetchone()
        if not fila or fila[0] is None:
            return _nuevo_params()
        d = json.loads(fila[0])
        if int(d.get("version", -1)) != VERSION or int(d.get("n", -1)) != N_ENTRADAS:
            logger.info("neurona_puentes: versión o forma distinta; se vuelve a lo neutro")
            return _nuevo_params()
        p = {k: np.array(d[k], dtype=float) for k in ("W", "b", "v")}
        return p if _sano(p) else _nuevo_params()
    except Exception as exc:
        logger.debug("neurona_puentes: estado ilegible (%s); se usa lo neutro", exc)
        return _nuevo_params()


def guardar(conn, p, stats=None):
    """Persiste los pesos. Devuelve True si quedaron escritos."""
    try:
        if not _sano(p):
            return False
        _tabla(conn)
        valor = json.dumps(dict(
            version=VERSION, n=N_ENTRADAS,
            stats=stats or {},
            **{k: p[k].tolist() for k in ("W", "b", "v")}))
        conn.execute(
            f"INSERT OR REPLACE INTO {_TABLA} (clave, valor, actualizado) VALUES (?, ?, ?)",
            ("pesos", valor, time.time()))
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("neurona_puentes: no se pudo guardar (%s)", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


# ───────────────────────── decisión (salida) ─────────────────────────

def _correccion(p, x):
    """tanh(W·x + b)·v. Con pesos a cero devuelve 0.0, no 0.5."""
    return float(np.tanh(p["W"] @ x + p["b"]) @ p["v"])


def multiplicador_params(p, rasgos, cfg=None):
    """La misma decisión pero con los pesos dados (para medir sin tocar la DB)."""
    cfg = cfg or _cfg()
    try:
        x = np.asarray(rasgos, dtype=float).reshape(-1)
        if x.shape[0] != N_ENTRADAS or not np.all(np.isfinite(x)):
            return cfg["techo"]
        c = _correccion(p, x)
        if c <= 0.0:
            return cfg["techo"]
        return float(min(cfg["techo"],
                         max(cfg["suelo"], cfg["techo"] - (cfg["techo"] - cfg["suelo"]) * min(1.0, c))))
    except Exception:
        return 1.0


def multiplicador(conn, rasgos):
    """EL CONTRATO. Devuelve cuánto vale este puente, entre suelo y techo.

    Cualquier fallo -> 1.0 (el motor sigue exactamente igual). Nunca lanza.

    La salida es monótona y solo puede ATENUAR: con corrección positiva baja
    el multiplicador hasta `suelo`; con corrección negativa o cero se queda en
    `techo` (1.0). No puede subir por encima de lo calibrado.
    """
    try:
        return multiplicador_params(cargar(conn), rasgos)
    except Exception as exc:
        logger.debug("neurona_puentes: fallo al decidir (%s); se usa el techo", exc)
        return 1.0


# ───────────────────────── entrenamiento ─────────────────────────

def entrenar(X, y, p=None, pasos=None, lr=None, l2=None, semilla=0):
    """Ajusta W, b, v por descenso de gradiente. numpy puro, sin GPU.

    X: (n, N_ENTRADAS), y: (n,) con 1 = el hub acertó el nodo, 0 = ruido.
    La salida se aprende con una logística: cuanto más debería atenuarse un
    puente, más alto debe ser c para que el multiplicador baje.

    Objetivo: que c(x) sea alto cuando y=0 (atenuar el ruido) y bajo cuando
    y=1 (no tocar el acierto). Es el sesgo de "primero no dañar" del molde:
    el costo de atenuar un acierto se pondera más que el de dejar pasar ruido.
    """
    cfg = _cfg()
    pasos = int(pasos or cfg["pasos"])
    lr = float(lr if lr is not None else cfg["lr"])
    l2 = float(l2 if l2 is not None else cfg["l2"])
    p = {k: v.copy() for k, v in (p or _nuevo_params()).items()}

    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] != N_ENTRADAS or len(y) != len(X) or len(X) == 0:
        return p, dict(n=0, perdida=float("nan"))
    y = np.asarray(y, dtype=float).reshape(-1)

    # El acierto pesa MÁS que el ruido: atenuar un puente bueno cuesta más
    # que dejar pasar uno malo (primero no dañar).
    w = np.where(y > 0.5, 2.0, 1.0)
    objetivo = np.where(y > 0.5, 0.0, 1.0)   # acierto -> c=0 (no tocar); ruido -> c=1
    n = float(len(X))

    perdida = float("nan")
    for _ in range(max(1, pasos)):
        h = np.tanh(X @ p["W"].T + p["b"])          # (n, ocultas)
        c = h @ p["v"]                              # (n,)
        e = (c - objetivo) * w                      # (n,)
        perdida = float(np.mean((c - objetivo) ** 2))
        gv = (h * e[:, None]).sum(0) / n + l2 * p["v"]
        dh = (e[:, None] * p["v"][None, :]) * (1.0 - h ** 2)
        gW = dh.T @ X / n + l2 * p["W"]
        gb = dh.sum(0) / n
        p["v"] -= lr * gv
        p["W"] -= lr * gW
        p["b"] -= lr * gb

    p = {k: np.clip(v, -50.0, 50.0) for k, v in p.items()}
    return (p, dict(n=int(len(X)), perdida=float(perdida))) if _sano(p) else (_nuevo_params(), dict(n=0, perdida=float("nan")))


def estado(conn):
    """Lo que un operador necesita para saber si la neurona está viva o neutra."""
    try:
        p = cargar(conn)
        return dict(activa=activa(), version=VERSION, entradas=N_ENTRADAS,
                    ocultas=N_OCULTAS, pesos_no_cero=int(np.count_nonzero(p["v"])),
                    neutra=es_neutra(p), cfg=_cfg())
    except Exception as exc:
        return dict(activa=False, error=str(exc))
