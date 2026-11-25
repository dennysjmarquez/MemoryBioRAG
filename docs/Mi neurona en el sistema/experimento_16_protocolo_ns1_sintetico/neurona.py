"""Neurona sináptica NS-1 (versión de laboratorio, experimento 16). numpy puro; no la usa el motor.

Qué hace: dada una pareja de recuerdos (a, b), estima la probabilidad CALIBRADA de que estén
relacionados de verdad. Solo sirve para ORDENAR el canal 2 (PROTOCOLO.md §7): no escribe pesos,
no decide nacimientos ni podas, no oculta nada.

Por qué es invariante por construcción: cada aguja depende SOLO del contenido de a y b y de una
tabla de frecuencias de referencia CONGELADA (con hash) calculada una vez sobre los recuerdos de
entrenamiento. Agregar recuerdos al sistema no cambia ninguna aguja de un par ya existente.
No usa el peso del piso, ni el grado, ni vecinos comunes, ni comunidades, ni tiempo, ni uso.
"""
import hashlib
import json
import math
import re

import numpy as np

_TOK = re.compile(r"[a-z0-9áéíóúñü]+")
DF_MIN = 5        # recorte del IDF: toda palabra con df <= 5 cuenta como "rara" por igual
COMUN = 0.5       # idf normalizado por debajo de esto = palabra común


def _toks(s):
    return _TOK.findall((s or "").lower())


def documento(concepto, rec):
    C = set(_toks(rec["contenido"]))
    N = {t for t in _toks(concepto.replace("_", " ")) if not any(ch.isdigit() for ch in t)}
    S_items = {x.strip().lower() for x in (rec["syn"] or "").split(",") if x.strip()}
    S = set(_toks(rec["syn"]))
    K = set(_toks((rec["sk"] or "").replace(",", " ")))
    return {"C": C, "N": N, "S": S, "Si": S_items, "K": K, "D": set(rec["dims"]), "cat": rec["cat"],
            "T": C | N | S | K}


class Referencia:
    """Tabla de frecuencias congelada. Se calcula UNA vez y se guarda con su hash."""

    def __init__(self, docs=None, estado=None):
        if estado:
            self.n, self.df = estado["n"], estado["df"]
        else:
            self.n = len(docs)
            self.df = {}
            for d in docs:
                for t in d["T"]:
                    self.df[t] = self.df.get(t, 0) + 1
        self._max = math.log((self.n + 1) / (DF_MIN + 1))

    def idf(self, t):
        return math.log((self.n + 1) / (max(self.df.get(t, 0), DF_MIN) + 1)) / self._max

    def huella(self):
        return hashlib.sha256(json.dumps([self.n, sorted(self.df.items())]).encode()).hexdigest()[:16]

    def estado(self):
        return {"n": self.n, "df": self.df}


NOMBRES = ["jac_contenido", "jac_contenido_idf", "solape_min_idf", "n_compartidas", "n_cortas_compartidas",
           "frac_masa_comun", "max_idf_compartida", "top3_idf_compartidas", "nombre_compartidas",
           "nombre_max_idf", "clave_cruzada", "jac_clave", "jac_sinonimos_item", "jac_sinonimos_idf",
           "jac_dimensiones", "n_dimensiones", "misma_categoria", "especificidad_min",
           "especificidad_dif", "frac_comun_max"]


def _jac(a, b):
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def _wjac(a, b, w):
    u = sum(w(t) for t in a | b)
    return sum(w(t) for t in a & b) / u if u else 0.0


def agujas(da, db, ref, cache=None):
    w = ref.idf

    def espec(d):
        if not d["T"]:
            return 0.0, 1.0
        v = [w(t) for t in d["T"]]
        return sum(v) / len(v), sum(1 for x in v if x < COMUN) / len(v)

    ea, ca = espec(da)
    eb, cb = espec(db)
    inter = da["T"] & db["T"]
    wi = sorted((w(t) for t in inter), reverse=True)
    masa = sum(wi)
    ma = sum(w(t) for t in da["T"]) or 1e-9
    mb = sum(w(t) for t in db["T"]) or 1e-9
    nint = da["N"] & db["N"]
    kx = len(da["K"] & db["T"]) + len(db["K"] & da["T"])
    return [
        _jac(da["C"], db["C"]),
        _wjac(da["C"], db["C"], w),
        masa / min(ma, mb),
        math.log1p(len(inter)),
        sum(1 for t in inter if len(t) <= 3),
        (sum(x for x in wi if x < COMUN) / masa) if masa else 0.0,
        wi[0] if wi else 0.0,
        sum(wi[:3]),
        len(nint),
        max((w(t) for t in nint), default=0.0),
        kx / max(1, len(da["K"]) + len(db["K"])),
        _jac(da["K"], db["K"]),
        _jac(da["Si"], db["Si"]),
        _wjac(da["S"], db["S"], w),
        _jac(da["D"], db["D"]),
        len(da["D"] & db["D"]),
        1.0 if da["cat"] == db["cat"] else 0.0,
        min(ea, eb),
        abs(ea - eb),
        max(ca, cb),
    ]


# ───────────────────────── modelo ─────────────────────────
def _isotonica(x, y):
    """Pool-adjacent-violators. Devuelve (umbrales, valores) para una función escalonada creciente."""
    o = np.argsort(x, kind="mergesort")
    xs, ys = x[o], y[o].astype(float)
    bloques = []  # [suma, cuenta, xmax]
    for xi, yi in zip(xs, ys):
        bloques.append([yi, 1.0, xi])
        while len(bloques) > 1 and bloques[-2][0] / bloques[-2][1] > bloques[-1][0] / bloques[-1][1]:
            s, c, xm = bloques.pop()
            bloques[-1][0] += s
            bloques[-1][1] += c
            bloques[-1][2] = xm
    return np.array([b[2] for b in bloques]), np.array([b[0] / b[1] for b in bloques])


class Neurona:
    def __init__(self, ref, ocultas=16, semilla=0):
        self.ref = ref
        self.h = ocultas
        self.semilla = semilla

    def _norm(self, X):
        return (X - self.mu) / self.sd

    def _crudo(self, X):
        Z = np.tanh(self._norm(X) @ self.W1 + self.b1)
        return (Z @ self.w2 + self.b2).ravel()

    def entrenar(self, X, y, Xv, yv, epocas=1500, lr=0.01, l2=1e-3):
        rng = np.random.default_rng(self.semilla)
        self.mu = X.mean(0)
        self.sd = X.std(0) + 1e-6
        d = X.shape[1]
        self.W1 = rng.normal(0, 1 / math.sqrt(d), (d, self.h))
        self.b1 = np.zeros(self.h)
        self.w2 = rng.normal(0, 1 / math.sqrt(self.h), (self.h, 1))
        self.b2 = np.zeros(1)
        P = [self.W1, self.b1, self.w2, self.b2]
        m = [np.zeros_like(p) for p in P]
        v = [np.zeros_like(p) for p in P]
        pos = y.mean()
        cw = np.where(y == 1, 0.5 / pos, 0.5 / (1 - pos))   # clases balanceadas
        Xn = self._norm(X)
        mejor, mejor_P, sin_mejora = 1e9, None, 0
        for ep in range(1, epocas + 1):
            Z = np.tanh(Xn @ self.W1 + self.b1)
            s = (Z @ self.w2 + self.b2).ravel()
            p = 1 / (1 + np.exp(-s))
            g = (p - y) * cw / len(y)
            gw2 = Z.T @ g[:, None] + l2 * self.w2
            gb2 = np.array([g.sum()])
            gZ = g[:, None] @ self.w2.T * (1 - Z ** 2)
            gW1 = Xn.T @ gZ + l2 * self.W1
            gb1 = gZ.sum(0)
            for i, gr in enumerate([gW1, gb1, gw2, gb2]):
                m[i] = 0.9 * m[i] + 0.1 * gr
                v[i] = 0.999 * v[i] + 0.001 * gr ** 2
                P[i] -= lr * (m[i] / (1 - 0.9 ** ep)) / (np.sqrt(v[i] / (1 - 0.999 ** ep)) + 1e-8)
            if ep % 25 == 0:
                sv = self._crudo(Xv)
                pv = np.clip(1 / (1 + np.exp(-sv)), 1e-6, 1 - 1e-6)
                cwv = np.where(yv == 1, 0.5 / yv.mean(), 0.5 / (1 - yv.mean()))
                loss = float(-(cwv * (yv * np.log(pv) + (1 - yv) * np.log(1 - pv))).mean())
                if loss < mejor - 1e-5:
                    mejor, mejor_P, sin_mejora = loss, [p.copy() for p in P], 0
                else:
                    sin_mejora += 1
                    if sin_mejora >= 8:
                        break
        self.W1, self.b1, self.w2, self.b2 = mejor_P
        self.epocas = ep
        return mejor

    def calibrar(self, X, y):
        self.iso_x, self.iso_y = _isotonica(self._crudo(X), y)

    def prob(self, X):
        s = self._crudo(X)
        i = np.searchsorted(self.iso_x, s, side="left")
        i = np.clip(i, 0, len(self.iso_y) - 1)
        return self.iso_y[i]

    def puntuar_crudo(self, X):
        """Para ORDENAR: puntuación cruda (estrictamente monótona con la red, sin empates de la isotónica)."""
        return self._crudo(X)


# ═════════════════════════ v2: memoria semántica aprendida sin etiquetas ═════════════════════════
class Semantica:
    """Significado aprendido por USO (semántica distribucional, sin etiquetas): dos palabras que aparecen
    rodeadas de las mismas palabras quedan cerca, aunque nunca aparezcan juntas (sinónimos). PPMI + SVD.

    Se calcula UNA vez sobre el texto (sin etiquetas) de los recuerdos existentes y se congela con hash:
    recuerdos agregados después no cambian ningún vector (invariancia por construcción)."""

    def __init__(self, docs, ref, k=48, df_min=2):
        df = {}
        for d in docs:
            for t in d["T"]:
                df[t] = df.get(t, 0) + 1
        vocab = sorted(t for t, c in df.items() if c >= df_min)
        self.idx = {t: i for i, t in enumerate(vocab)}
        V = len(vocab)
        M = np.zeros((V, V))
        for d in docs:
            ids = [self.idx[t] for t in d["T"] if t in self.idx]
            for i in ids:
                M[i, ids] += 1.0
        np.fill_diagonal(M, 0.0)
        tot = M.sum()
        fila = M.sum(1)
        col = M.sum(0) ** 0.75
        col = col / col.sum()
        with np.errstate(divide="ignore", invalid="ignore"):
            pmi = np.log((M / tot) / (np.outer(fila / tot, col) + 1e-12) + 1e-12)
        P = np.where(M > 0, np.maximum(pmi, 0.0), 0.0)
        U, S, _ = np.linalg.svd(P, full_matrices=False)
        E = U[:, :k] * np.sqrt(S[:k])
        E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-12
        self.E = E
        self.ref = ref
        self._h = hashlib.sha256(np.round(E, 6).tobytes()).hexdigest()[:16]

    def huella(self):
        return self._h

    def vec_doc(self, d, solo_raras=False):
        v = np.zeros(self.E.shape[1])
        for t in d["T"]:
            i = self.idx.get(t)
            if i is None:
                continue
            w = self.ref.idf(t)
            if solo_raras and w < COMUN:
                continue
            v += w * self.E[i]
        n = np.linalg.norm(v)
        return v / n if n else v

    def raras(self, d):
        ids = [self.idx[t] for t in d["T"] if t in self.idx and self.ref.idf(t) >= COMUN]
        return self.E[ids] if ids else np.zeros((0, self.E.shape[1]))


NOMBRES_V2 = NOMBRES + ["sem_coseno", "sem_coseno_raras", "sem_alineacion"]


def agujas_v2(da, db, ref, sem, cache):
    """Agujas v1 + 3 agujas semánticas. `cache` guarda por recuerdo sus vectores (no cambia nada)."""
    base = agujas(da, db, ref)
    for d in (da, db):
        if id(d) not in cache:
            cache[id(d)] = (sem.vec_doc(d), sem.vec_doc(d, True), sem.raras(d))
    va, ra, Ra = cache[id(da)]
    vb, rb, Rb = cache[id(db)]
    if len(Ra) and len(Rb):
        C = Ra @ Rb.T
        alin = 0.5 * (C.max(1).mean() + C.max(0).mean())
    else:
        alin = 0.0
    return base + [float(va @ vb), float(ra @ rb), float(alin)]
