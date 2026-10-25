"""Neurona asociativa de BioRAG (v35): ¿dos recuerdos de verdad tienen que ver?

Viene del experimento 11 (`docs/Mi neurona en el sistema/experimento_11_neurona_asociativa/`).
Es la misma fórmula, ya cerrada: nace calibrada de fábrica y NO aprende de la memoria del
usuario. Dados dos recuerdos devuelve una FUERZA de 0 a 1.

ESTADO EN v35.0 (cierre, 2026-10-25): construida, calibrada, examinada y cerrada, pero el
motor NO la llama. Se probó que pusiera el peso de nacimiento de cada sinapsis (commit
dd85fcf, experimento 12): la QA salió idéntica, así que se revirtió (76fe11c) y
`core/sinapsis.py` volvió a los pesos a mano. Cortar sinapsis al nacer baja el recall
(experimento 13), así que tampoco hace eso. Su lugar propuesto, medido en copia y pendiente:
elegir qué asociaciones ve el agente (canal 2). Ver README, sección v35.0.

Lo que sigue describe la conversión a peso tal como se diseñó (y se probó) en el experimento 12;
`peso_desde_fuerza` y `Juez.peso` se conservan para ese uso futuro:

    Cuando el motor decide crear una sinapsis (con sus reglas de siempre), la neurona
    decidiría con qué fuerza nace. No crea ni corta sinapsis: el conjunto de conexiones es
    exactamente el mismo de antes; solo cambia el peso.

    fuerza = 1 / (1 + e^-z)
    z      = -1 + 2·parecido + 1·semantica + 1·rareza_max + 4·episodio + 1·etiquetas
    peso   = 0.5 + 0.5·fuerza                       (siempre entre 0.5 y 1.0)

Por qué `peso = 0.5 + 0.5·fuerza`:
  - Ninguna sinapsis nueva nace por debajo de 0.5. El motor usa 0.5 como filtro de
    asociaciones (canal 2) y poda por debajo de 0.05; así ninguna conexión queda "cortada"
    de hecho por nacer débil. Esto respeta "nunca bajar el recall".
  - El ORDEN entre las sinapsis de un recuerdo sigue a la neurona. La expansión por el grafo
    toma los 6 vecinos de mayor peso: con la neurona, son los que más tienen que ver.
  - fuerza 0.6 → peso 0.80, el umbral "peso alto" del DMN. En el examen de Dennys, con
    fuerza ≥ 0.6, 13 de 14 sinapsis existentes eran buenas (README del experimento, V2.18).

Las 5 agujas (todas 0..1, calculadas sobre la propia memoria, en cualquier idioma):
  parecido     coseno tf-idf de las raíces de 7 letras
  semantica    coseno en un espacio LSA de 100 dimensiones (plegado: un recuerdo nuevo se
               proyecta con los vectores de raíz guardados; no hace falta recalcular nada)
  rareza_max   la raíz compartida más rara (idf normalizado)
  episodio     ¿se guardaron cerca en el tiempo? (solo si en ESTA memoria el tiempo
               coincide con el texto: `fiab_episodio`, medido sin verdad)
  etiquetas    dims compartidas (Jaccard), solo si en ESTA memoria coinciden con el texto

Estado (lo que la neurona necesita saber de la memoria) en dos tablas propias:
  neurona_asociativa_estado (clave, valor)   n, fiabilidades, sello de construcción
  neurona_asociativa_raices (raiz, idf, vec) idf y vector LSA de cada raíz
Se construye solo la primera vez y se rehace cuando la memoria crece un 10 % (+10).
Para memorias grandes se construye sobre una muestra fija de MUESTRA_MAX recuerdos, así el
costo tiene techo. Cada decisión por par es tiempo constante (no depende del tamaño de la DB).

Si algo falla, la neurona se aparta: el motor usa el peso a mano de siempre. Nunca rompe
un guardado. Interruptor: BIORAG_NEURONA_ASOCIATIVA=0 la apaga (vuelve al peso a mano).
Solo numpy, como el resto del motor.
"""
import logging
import math
import os
import re
import sqlite3
import time
import unicodedata

import numpy as np

logger = logging.getLogger(__name__)

VERSION = "asoc-1"            # cambia si cambian las agujas o la construcción → se reconstruye
PISO = {"sesgo": -1.0, "parecido": 2.0, "semantica": 1.0, "rareza_max": 1.0,
        "episodio": 4.0, "etiquetas": 1.0}
PESO_MIN = 0.5                # peso = PESO_MIN + (1 - PESO_MIN) * fuerza

LARGO_RAIZ = 7
DF_MAX = 0.15
DIM_SEM = 100
VENTANA_EPISODIO = 10
VECINDAD_TIEMPO = 60          # más allá de 60 recuerdos, episodio aporta < 0.01 a z: se toma 0
HUECO_MAX = 7 * 86400         # guardia del motor: si entre los dos pasaron más de 7 días reales,
                              # no "se vivieron juntos" aunque no haya recuerdos en medio (p. ej. volver
                              # tras 2 meses). En la memoria de Dennys el 99 % de los pares a ≤10
                              # recuerdos de distancia están a menos de 80 h: la guardia no cambia
                              # la fórmula calibrada en el uso normal.
MUESTRA_MAX = 2000            # techo de recuerdos para construir el estado (costo acotado)
CRECER = 0.10                 # se reconstruye cuando la memoria crece un 10 % (+10 recuerdos)
_BLOQUE = 2048

_TOK = re.compile(r"[a-z0-9]+")
_CACHE = {}                   # {ruta_db: (sello, _Estado)}


def activa():
    return os.getenv("BIORAG_NEURONA_ASOCIATIVA", "1") != "0"


def tokens(texto):
    """Raíces universales (primeras 7 letras), sin lista de palabras vacías de ningún idioma."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("_", " ").replace("-", " ")
    return [w[:LARGO_RAIZ] for w in _TOK.findall(t) if len(w) >= 3 and not w.isdigit()]


def texto_recuerdo(concepto, contenido):
    return f"{(concepto or '').replace('_', ' ')}. {contenido or ''}"


def peso_desde_fuerza(f):
    return round(PESO_MIN + (1.0 - PESO_MIN) * float(f), 3)


def fuerza_desde_agujas(parecido, semantica, rareza_max, episodio, etiquetas):
    z = (PISO["sesgo"] + PISO["parecido"] * parecido + PISO["semantica"] * semantica
         + PISO["rareza_max"] * rareza_max + PISO["episodio"] * episodio + PISO["etiquetas"] * etiquetas)
    return 1.0 / (1.0 + math.exp(-z))


def _auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    todo = np.concatenate([pos, neg])
    _, inv, cnt = np.unique(todo, return_inverse=True, return_counts=True)
    r = (np.cumsum(cnt) - (cnt - 1) / 2.0)[inv]
    n1 = len(pos)
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * len(neg)))


class _Estado:
    def __init__(self, n, logn, idx, idf, V, fiab_ep, fiab_et):
        self.n, self.logn, self.idx, self.idf, self.V = n, logn, idx, idf, V
        self.fiab_episodio, self.fiab_etiquetas = fiab_ep, fiab_et

    def vector(self, texto):
        """(raíces del vocabulario, vector tf-idf normalizado {j: x}, vector LSA normalizado)."""
        cuenta = {}
        for w in tokens(texto):
            j = self.idx.get(w)
            if j is not None:
                cuenta[j] = cuenta.get(j, 0) + 1
        if not cuenta:
            return frozenset(), {}, None
        js = np.fromiter(cuenta.keys(), dtype=np.int64)
        x = np.log1p(np.fromiter(cuenta.values(), dtype=np.float64)) * self.idf[js]
        nx = float(np.linalg.norm(x)) or 1e-9
        x = x / nx
        tf = dict(zip(js.tolist(), x.tolist()))
        d = None
        if self.V is not None and self.V.shape[1]:
            d = x @ self.V[js].astype(np.float64)
            nd = float(np.linalg.norm(d))
            d = d / nd if nd > 1e-9 else None
        return frozenset(cuenta), tf, d


# ───────────────────────────── construcción del estado ─────────────────────────────

def _ruta_db(cursor):
    try:
        for _, nombre, ruta in cursor.execute("PRAGMA database_list").fetchall():
            if nombre == "main":
                return ruta or f":memory:{id(cursor.connection)}"
    except sqlite3.Error:
        pass
    return f":memory:{id(cursor.connection)}"


def _crear_tablas(cursor):
    cursor.execute("CREATE TABLE IF NOT EXISTS neurona_asociativa_estado (clave TEXT PRIMARY KEY, valor TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS neurona_asociativa_raices "
                   "(raiz TEXT PRIMARY KEY, j INTEGER, idf REAL, vec BLOB)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lp_creado_en ON largo_plazo(creado_en)")


def _leer_estado_meta(cursor):
    try:
        return dict(cursor.execute("SELECT clave, valor FROM neurona_asociativa_estado").fetchall())
    except sqlite3.OperationalError:
        return {}


def _fiabilidad(S, Ssem, n, cerca, semilla, pos_t=None, muestras=20000):
    """¿En ESTA memoria la señal (tiempo o etiquetas) coincide con el texto? Sin verdad.
    Igual que el experimento 11: AUC .5 → 0;  AUC ≥ .80 → 1."""
    rng = np.random.default_rng(semilla)
    a = rng.integers(0, n, muestras)
    b = rng.integers(0, n, muestras)
    ok = a != b
    a, b = a[ok], b[ok]
    sim = np.maximum(S(a, b), 0) + np.maximum(Ssem(a, b), 0)
    junta = np.array([cerca(int(x), int(y)) for x, y in zip(a, b)])
    if pos_t is not None:
        inv = np.argsort(pos_t)
        d = rng.integers(1, VENTANA_EPISODIO + 1, muestras // 4)
        i = rng.integers(0, max(n - VENTANA_EPISODIO - 1, 1), muestras // 4)
        ea, eb = inv[i], inv[np.minimum(i + d, n - 1)]
        ok2 = ea != eb
        sim = np.concatenate([sim, np.maximum(S(ea[ok2], eb[ok2]), 0) + np.maximum(Ssem(ea[ok2], eb[ok2]), 0)])
        junta = np.concatenate([junta, np.ones(int(ok2.sum()), bool)])
    if junta.sum() < 20 or (~junta).sum() < 20:
        return 0.0
    return float(np.clip((_auc(sim[junta], sim[~junta]) - 0.5) / 0.30, 0.0, 1.0))


def construir(cursor, semilla=0):
    """Calcula el estado de la neurona desde la memoria y lo guarda en sus tablas.
    Devuelve el _Estado o None si la memoria es demasiado chica (< 3 recuerdos)."""
    t0 = time.time()
    filas = cursor.execute("SELECT concepto, COALESCE(contenido,''), creado_en FROM largo_plazo "
                           "WHERE estado='activo' ORDER BY concepto").fetchall()
    n_total = len(filas)
    if n_total < 3:
        return None
    if n_total > MUESTRA_MAX:
        elegidos = np.sort(np.random.default_rng(semilla).choice(n_total, MUESTRA_MAX, replace=False))
        filas = [filas[i] for i in elegidos]
    n = len(filas)
    conceptos = [f[0] for f in filas]
    toks = [tokens(texto_recuerdo(f[0], f[1])) for f in filas]
    df = {}
    for ts in toks:
        for w in set(ts):
            df[w] = df.get(w, 0) + 1
    tope = max(2, int(DF_MAX * n))
    vocab = sorted(w for w, d in df.items() if 2 <= d <= tope)
    idx = {w: i for i, w in enumerate(vocab)}
    logn = math.log(max(n, 2))
    idf = np.array([math.log(max(n, 2) / df[w]) for w in vocab], dtype=np.float64)
    nv = len(vocab)

    # X (n × vocab) disperso por filas: tf-idf log1p, normalizado
    filas_x = []
    for ts in toks:
        c = {}
        for w in ts:
            j = idx.get(w)
            if j is not None:
                c[j] = c.get(j, 0) + 1
        if c:
            js = np.fromiter(c.keys(), dtype=np.int64)
            x = np.log1p(np.fromiter(c.values(), dtype=np.float64)) * idf[js]
            x /= max(float(np.linalg.norm(x)), 1e-9)
        else:
            js, x = np.zeros(0, np.int64), np.zeros(0)
        filas_x.append((js, x))

    def bloque(lo, hi):
        B = np.zeros((n, hi - lo), dtype=np.float64)
        for i, (js, x) in enumerate(filas_x):
            m = (js >= lo) & (js < hi)
            if m.any():
                B[i, js[m] - lo] = x[m]
        return B

    G = np.zeros((n, n), dtype=np.float64)
    for lo in range(0, max(nv, 1), _BLOQUE):
        Xb = bloque(lo, min(lo + _BLOQUE, nv))
        G += Xb @ Xb.T
    k = max(1, min(DIM_SEM, n - 1))
    L, U = np.linalg.eigh(G)
    L, U = L[::-1][:k], U[:, ::-1][:, :k]
    raizL = np.sqrt(np.maximum(L, 0))
    D = U * raizL[None, :]
    D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
    inv_raiz = np.where(raizL > 1e-9, 1.0 / np.maximum(raizL, 1e-12), 0.0)
    V = np.zeros((nv, k), dtype=np.float32)
    for lo in range(0, max(nv, 1), _BLOQUE):
        hi = min(lo + _BLOQUE, nv)
        V[lo:hi] = ((bloque(lo, hi).T @ U) * inv_raiz[None, :]).astype(np.float32)

    def S(a, b):
        return G[a, b]

    def Ssem(a, b):
        return np.einsum("ij,ij->i", D[a], D[b])

    # fiabilidad del tiempo
    fiab_ep = 0.0
    t_min = min((f[2] for f in filas if f[2]), default=0.0)
    orden = np.array([float(f[2]) if f[2] else t_min for f in filas])
    if n >= 3:
        o = np.argsort(orden, kind="mergesort")
        pos_t = np.empty(n, dtype=np.int64)
        pos_t[o] = np.arange(n)
        fiab_ep = _fiabilidad(S, Ssem, n, lambda a, b: abs(int(pos_t[a]) - int(pos_t[b])) <= VENTANA_EPISODIO,
                              semilla, pos_t=pos_t)
    # fiabilidad de las etiquetas (dims)
    fiab_et = 0.0
    pos = {c: i for i, c in enumerate(conceptos)}
    etq = [set() for _ in range(n)]
    try:
        for a, d in cursor.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones").fetchall():
            i = pos.get(a)
            if i is not None:
                etq[i].add(d)
    except sqlite3.OperationalError:
        pass
    if any(etq):
        fiab_et = _fiabilidad(S, Ssem, n, lambda a, b: bool(etq[a] & etq[b]), semilla)

    _crear_tablas(cursor)
    sello = f"{VERSION}:{n_total}:{time.time():.6f}"
    cursor.execute("DELETE FROM neurona_asociativa_raices")
    cursor.executemany("INSERT INTO neurona_asociativa_raices (raiz, j, idf, vec) VALUES (?,?,?,?)",
                       ((w, j, float(idf[j]), V[j].tobytes()) for w, j in idx.items()))
    cursor.execute("DELETE FROM neurona_asociativa_estado")
    cursor.executemany("INSERT INTO neurona_asociativa_estado (clave, valor) VALUES (?,?)", [
        ("version", VERSION), ("n_total", str(n_total)), ("n_muestra", str(n)), ("logn", repr(logn)),
        ("k", str(k)), ("fiab_episodio", repr(fiab_ep)), ("fiab_etiquetas", repr(fiab_et)),
        ("sello", sello), ("construido_en", repr(time.time())), ("segundos", f"{time.time() - t0:.3f}")])
    est = _Estado(n, logn, idx, idf, V, fiab_ep, fiab_et)
    _CACHE[_ruta_db(cursor)] = (sello, est)
    logger.info("neurona asociativa: estado construido (%d recuerdos, %d raíces, %.2fs)", n, nv, time.time() - t0)
    return est


def _cargar(cursor, meta):
    filas = cursor.execute("SELECT raiz, j, idf, vec FROM neurona_asociativa_raices").fetchall()
    k = int(meta["k"])
    nv = len(filas)
    idx, idf, V = {}, np.zeros(nv), np.zeros((nv, k), dtype=np.float32)
    for raiz, j, i_, vec in filas:
        idx[raiz] = j
        idf[j] = i_
        V[j] = np.frombuffer(vec, dtype=np.float32, count=k)
    return _Estado(int(meta["n_muestra"]), float(meta["logn"]), idx, idf, V,
                   float(meta["fiab_episodio"]), float(meta["fiab_etiquetas"]))


def estado(cursor):
    """El estado vigente (lo construye o lo rehace si hace falta). None = la neurona se aparta."""
    meta = _leer_estado_meta(cursor)
    n_act = cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
    vigente = (meta.get("version") == VERSION and "n_total" in meta
               and n_act < int(meta["n_total"]) * (1 + CRECER) + 10)
    if not vigente:
        return construir(cursor) if n_act >= 3 else None
    ruta = _ruta_db(cursor)
    sello = meta.get("sello")
    c = _CACHE.get(ruta)
    if c and c[0] == sello:
        return c[1]
    est = _cargar(cursor, meta)
    _CACHE[ruta] = (sello, est)
    return est


# ───────────────────────────── el juez (por guardado) ─────────────────────────────

class Juez:
    """Se crea una vez por guardado. `peso(destino, contenido, peso_mano)` decide el peso de
    nacimiento de la sinapsis concepto→destino. Si no puede decidir, devuelve peso_mano."""

    def __init__(self, cursor, concepto, contenido=None):
        self.cursor = cursor
        self.concepto = concepto
        self.est = None
        self.decisiones = 0
        try:
            if not activa():
                return
            est = estado(cursor)
            if est is None:
                return
            if contenido is None:
                contenido = self._contenido(concepto)
            self.set_a, self.tf_a, self.d_a = est.vector(texto_recuerdo(concepto, contenido))
            self.dims_a = self._dims(concepto)
            self.pos = self._vecindad_tiempo(concepto)
            self.est = est
        except Exception as exc:          # la neurona nunca rompe un guardado
            logger.warning("neurona asociativa apartada (%s): se usa el peso a mano", exc)
            self.est = None

    def _contenido(self, concepto):
        """Contenido del recuerdo: en largo plazo o, si aún no se consolidó, en corto plazo."""
        for tabla in ("largo_plazo", "corto_plazo"):
            try:
                fila = self.cursor.execute(f"SELECT contenido FROM {tabla} WHERE concepto = ?", (concepto,)).fetchone()
            except sqlite3.OperationalError:
                fila = None
            if fila and fila[0]:
                return fila[0]
        return ""

    def _dims(self, concepto):
        d = set()
        for tabla in ("largo_plazo_dimensiones", "corto_plazo_dimensiones"):
            try:
                d.update(r[0] for r in self.cursor.execute(
                    f"SELECT dimension_id FROM {tabla} WHERE concepto = ?", (concepto,)).fetchall())
            except sqlite3.OperationalError:
                pass
        return d

    def _vecindad_tiempo(self, concepto):
        """{concepto: distancia en orden de llegada} para los recuerdos cercanos en el tiempo."""
        fila = self.cursor.execute("SELECT creado_en FROM largo_plazo WHERE concepto = ? AND estado='activo'",
                                   (concepto,)).fetchone()
        pos = {}
        if fila is None or fila[0] is None:      # aún en corto plazo: es el más nuevo
            t = time.time()
            antes = self.cursor.execute(
                "SELECT concepto, creado_en FROM largo_plazo WHERE estado='activo' AND creado_en IS NOT NULL "
                "ORDER BY creado_en DESC, concepto DESC LIMIT ?", (VECINDAD_TIEMPO,)).fetchall()
            despues = []
        else:
            t = fila[0]
            antes = self.cursor.execute(
                "SELECT concepto, creado_en FROM largo_plazo WHERE estado='activo' "
                "AND (creado_en < ? OR (creado_en = ? AND concepto < ?)) "
                "ORDER BY creado_en DESC, concepto DESC LIMIT ?", (t, t, concepto, VECINDAD_TIEMPO)).fetchall()
            despues = self.cursor.execute(
                "SELECT concepto, creado_en FROM largo_plazo WHERE estado='activo' "
                "AND (creado_en > ? OR (creado_en = ? AND concepto > ?)) "
                "ORDER BY creado_en ASC, concepto ASC LIMIT ?", (t, t, concepto, VECINDAD_TIEMPO)).fetchall()
        for lista in (antes, despues):
            for d, (c, tc) in enumerate(lista, 1):
                if abs(float(t) - float(tc)) <= HUECO_MAX:
                    pos[c] = d
        return pos

    def agujas(self, destino, contenido=None):
        est = self.est
        if contenido is None:
            contenido = self._contenido(destino)
        set_b, tf_b, d_b = est.vector(texto_recuerdo(destino, contenido))
        com = self.set_a & set_b
        parecido = max(0.0, sum(self.tf_a[j] * tf_b[j] for j in com))
        semantica = max(0.0, float(self.d_a @ d_b)) if (self.d_a is not None and d_b is not None) else 0.0
        rareza = max((est.idf[j] / est.logn for j in com), default=0.0)
        ep = 0.0
        if est.fiab_episodio > 0:
            dist = self.pos.get(destino)
            if dist is not None:
                ep = math.exp(-dist / VENTANA_EPISODIO) * est.fiab_episodio
        et = 0.0
        if est.fiab_etiquetas > 0:
            dims_b = self._dims(destino)
            u = self.dims_a | dims_b
            if u:
                et = len(self.dims_a & dims_b) / len(u) * est.fiab_etiquetas
        return tuple(min(1.0, max(0.0, float(v))) for v in (parecido, semantica, rareza, ep, et))

    def fuerza(self, destino, contenido=None):
        if self.est is None:
            return None
        try:
            return fuerza_desde_agujas(*self.agujas(destino, contenido))
        except Exception as exc:
            logger.warning("neurona asociativa: no pudo decidir %s→%s (%s)", self.concepto, destino, exc)
            return None

    def peso(self, destino, contenido=None, peso_mano=0.5):
        f = self.fuerza(destino, contenido)
        if f is None:
            return peso_mano
        self.decisiones += 1
        return peso_desde_fuerza(f)
