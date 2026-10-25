"""Agujas universales de la neurona asociativa (experimento 11, versión 2).

Una "aguja" es una señal en escala 0..1 sobre un PAR de recuerdos (A, B). Son
UNIVERSALES: no miran qué palabras hay, sino CÓMO se relacionan los dos
recuerdos dentro de su propia memoria. Por eso las mismas agujas se pueden
calcular en cualquier memoria e idioma (español, inglés, portugués, código,
chat, noticias, diccionario...).

Cada aguja copia una función del hipocampo (ver README, sección 1):

  parecido        corteza: cuánto se parecen sus palabras (coseno tf-idf)
  semantica       corteza: cuánto se parecen en significado (LSA, 2º orden)
  rareza_max      giro dentado: la pista compartida más rara (una sola pista
                  muy rara ya dice mucho; una palabra común no dice nada)
  rareza_media    giro dentado: qué tan raras son, en promedio, las pistas
  pistas_raras    giro dentado: cuántas pistas raras distintas comparten
  cobertura       CA3: qué parte de lo importante del más corto está en el otro
  mutuo           CA1 / inhibición lateral: ¿A está entre los más cercanos de B
                  Y B entre los de A? (k-ganadores)
  vecinos         CA3 (completar patrón): ¿tienen los mismos vecinos cercanos?
  hub             escalado sináptico (homeostasis): ¿alguno de los dos se
                  parece "a todo"? (recuerdo genérico = conexión poco fiable)
  una_sola        Dennys: ¿se tocan por UNA sola palabra?
  episodio        células de tiempo (hipocampo/entorrinal lateral): ¿se
                  guardaron cerca en el tiempo? (v2)
  etiquetas       corteza prefrontal (esquemas): ¿comparten etiquetas gruesas,
                  como las dims del motor? (v2)

`episodio` y `etiquetas` son OPCIONALES y se AUTO-REGULAN: cada memoria mide
sola (sin verdad, sin nadie que le diga) si en ELLA el tiempo / las etiquetas
coinciden con lo que dice el texto. Si no coinciden, la aguja se apaga (vale 0).
Si la memoria no tiene tiempo o etiquetas, también vale 0. Así la neurona nunca
confía a ciegas en el reloj.

Nota histórica: la v1 calculaba una aguja más, `corto` (¿alguno es muy corto?).
Se probó y no separa nada (AUC ~.50 en las 3 memorias); en la v2 se quitó.

Solo numpy (mismas dependencias que el motor).
"""
import math
import re
import unicodedata

import numpy as np

VERSION_AGUJAS = 2
NOMBRES = ["parecido", "semantica", "rareza_max", "rareza_media", "pistas_raras",
           "cobertura", "mutuo", "vecinos", "hub", "una_sola", "episodio", "etiquetas"]

# CONTEXTO: no son agujas del piso. Le cuentan a la corrección EN QUÉ TIPO de memoria está
# (textos cortos o largos, si el tiempo y las etiquetas valen algo aquí). Son los "pesos que
# dependen del contexto": la misma pista puede valer más en una memoria que en otra.
CONTEXTO = ["largo", "fiab_episodio", "fiab_etiquetas"]
NOMBRES_TODAS = NOMBRES + CONTEXTO

_TOK = re.compile(r"[a-z0-9]+")
LARGO_RAIZ = 7          # raíz universal: primeras 7 letras (busqueda/busquedas -> busqued)
DF_MAX = 0.15           # palabras en más del 15 % de los recuerdos = "de relleno" en ESA memoria
DIM_SEM = 100           # dimensiones del espacio semántico (como el PPMI-SVD del motor)
K_VECINOS = 10
VENTANA_EPISODIO = 10   # "cerca en el tiempo" = a unos 10 recuerdos de distancia en el orden de llegada
VECINOS_TIEMPO = 2      # candidatos extra: los 2 recuerdos guardados justo antes y justo después


def tokens(texto):
    """Raíces universales de un texto (sin lista de palabras vacías de ningún idioma)."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("_", " ").replace("-", " ")
    return [w[:LARGO_RAIZ] for w in _TOK.findall(t) if len(w) >= 3 and not w.isdigit()]


def _auc(pos, neg):
    """P(un valor de `pos` > uno de `neg`), empates = 1/2. Vectorizado, sin scipy."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    todo = np.concatenate([pos, neg])
    _, inv, cnt = np.unique(todo, return_inverse=True, return_counts=True)
    r = (np.cumsum(cnt) - (cnt - 1) / 2.0)[inv]
    n1 = len(pos)
    return float((r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * len(neg)))


class Memoria:
    """Estadísticas de UNA memoria (corpus) que las agujas necesitan.

    Todo se calcula desde la propia memoria: df/idf de cada raíz, vectores
    tf-idf, espacio semántico (LSA), vecinos cercanos, "hub" y, si existen, el
    orden de llegada y las etiquetas. Nada viene de afuera.

    orden:      número por recuerdo (fecha, id creciente...) o None.
    etiquetas:  conjunto de etiquetas por recuerdo (dims, género...) o None.
    """

    def __init__(self, textos, orden=None, etiquetas=None, semilla=0):
        self.n = n = len(textos)
        toks = [tokens(t) for t in textos]
        df = {}
        for ts in toks:
            for w in set(ts):
                df[w] = df.get(w, 0) + 1
        tope = max(2, int(DF_MAX * n))
        vocab = sorted(w for w, d in df.items() if 2 <= d <= tope)
        self.idx = {w: i for i, w in enumerate(vocab)}
        self.logn = math.log(max(n, 2))
        self.idf = np.array([math.log(max(n, 2) / df[w]) for w in vocab], dtype=np.float32)
        self.idf_n = self.idf / self.logn                       # 0..1
        self.sets = [frozenset(self.idx[w] for w in ts if w in self.idx) for ts in toks]
        self.largo = np.array([len(ts) for ts in toks], dtype=np.float32)
        X = np.zeros((n, max(len(vocab), 1)), dtype=np.float32)
        for i, ts in enumerate(toks):
            for w in ts:
                j = self.idx.get(w)
                if j is not None:
                    X[i, j] += 1.0
        if vocab:
            X = np.log1p(X) * self.idf[None, :]
        X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-9)
        self.X = X
        S = X @ X.T                                             # coseno tf-idf
        np.fill_diagonal(S, -1.0)
        self.S = S
        # Espacio semántico (LSA) por la matriz de Gram: G = X X^T = U L U^T
        if n >= 2:
            G = X @ X.T
            L, U = np.linalg.eigh(G.astype(np.float64))
            k = max(1, min(DIM_SEM, n - 1))
            L, U = L[::-1][:k], U[:, ::-1][:, :k]
            D = (U * np.sqrt(np.maximum(L, 0))[None, :]).astype(np.float32)
            D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
            Ssem = D @ D.T
        else:
            Ssem = np.zeros((n, n), dtype=np.float32)
        np.fill_diagonal(Ssem, -1.0)
        self.Ssem = Ssem
        # Rango de cada recuerdo en la lista de cercanos del otro (por parecido)
        orden_s = np.argsort(-S, axis=1, kind="mergesort")
        self.rango = np.empty_like(orden_s)
        filas = np.arange(n)[:, None]
        self.rango[filas, orden_s] = np.arange(n)[None, :]
        # Vecinos cercanos en el espacio semántico (solo los que de verdad se parecen algo: > 0)
        top = np.argsort(-Ssem, axis=1, kind="mergesort")[:, :K_VECINOS]
        self.knn = [frozenset(int(j) for j in top[i] if Ssem[i, j] > 0) for i in range(n)]
        # Hub: a cuántos recuerdos se parece "algo" (coseno > .1), como fracción de la memoria
        # que se parece a MENOS recuerdos que él (empates no suben: si todos son iguales, 0)
        cuantos = (S > 0.10).sum(axis=1).astype(np.float64)
        self.hub = (np.searchsorted(np.sort(cuantos), cuantos, side="left") / max(n - 1, 1)).astype(np.float32)
        # ---- tiempo (episodio) ----
        self.pos_t = None
        self.fiab_episodio = 0.0
        if orden is not None and n >= 3:
            o = np.argsort(np.asarray(orden, dtype=np.float64), kind="mergesort")
            self.pos_t = np.empty(n, dtype=np.int64)
            self.pos_t[o] = np.arange(n)
            self.fiab_episodio = self._fiabilidad(
                lambda a, b: abs(int(self.pos_t[a]) - int(self.pos_t[b])) <= VENTANA_EPISODIO, semilla, tiempo=True)
        # ---- etiquetas (dims) ----
        self.etq = None
        self.fiab_etiquetas = 0.0
        if etiquetas is not None and n >= 3:
            self.etq = [frozenset(e or ()) for e in etiquetas]
            if any(self.etq):
                self.fiab_etiquetas = self._fiabilidad(lambda a, b: bool(self.etq[a] & self.etq[b]), semilla)

    def _fiabilidad(self, cerca, semilla, tiempo=False, muestras=20000):
        """¿En ESTA memoria la señal coincide con el texto? Sin verdad: compara el
        parecido de texto de los pares que la señal junta contra pares al azar.
        AUC .5 (no coincide) -> 0;  AUC >= .80 -> 1."""
        rng = np.random.default_rng(semilla)
        a = rng.integers(0, self.n, muestras)
        b = rng.integers(0, self.n, muestras)
        ok = a != b
        a, b = a[ok], b[ok]
        sim = np.maximum(self.S[a, b], 0) + np.maximum(self.Ssem[a, b], 0)
        junta = np.array([cerca(int(x), int(y)) for x, y in zip(a, b)])
        if tiempo:
            # los pares cercanos en el tiempo son raros al azar: se agregan pares (i, i+d) a propósito
            inv = np.argsort(self.pos_t)
            d = rng.integers(1, VENTANA_EPISODIO + 1, muestras // 4)
            i = rng.integers(0, max(self.n - VENTANA_EPISODIO - 1, 1), muestras // 4)
            ea, eb = inv[i], inv[np.minimum(i + d, self.n - 1)]
            ok2 = ea != eb
            sim = np.concatenate([sim, np.maximum(self.S[ea[ok2], eb[ok2]], 0) + np.maximum(self.Ssem[ea[ok2], eb[ok2]], 0)])
            junta = np.concatenate([junta, np.ones(int(ok2.sum()), bool)])
        if junta.sum() < 20 or (~junta).sum() < 20:
            return 0.0
        auc = _auc(sim[junta], sim[~junta])
        return float(np.clip((auc - 0.5) / 0.30, 0.0, 1.0))

    def candidatos(self, por_nodo=30, rng=None):
        """Los pares que un motor mecánico propondría: comparten al menos una
        raíz (como las reglas de hoy) o son vecinos semánticos (como PPMI).
        Hasta `por_nodo` por recuerdo (MAX_FANOUT del motor = 30): 2/3 los más
        parecidos y 1/3 al azar entre los que solo comparten alguna palabra.
        v2: si la memoria tiene tiempo, se suman los VECINOS_TIEMPO recuerdos
        guardados justo antes y justo después (lo que se vivió junto)."""
        rng = rng or np.random.default_rng(0)
        inv = {}
        for i, s in enumerate(self.sets):
            for j in s:
                inv.setdefault(j, []).append(i)
        pares = set()
        for a in range(self.n):
            cand = set()
            for j in self.sets[a]:
                cand.update(inv[j])
            cand.update(self.knn[a])
            cand.discard(a)
            cand = sorted(cand)
            if len(cand) > por_nodo:
                cand.sort(key=lambda b: -self.S[a, b])
                top = cand[:por_nodo * 2 // 3]
                resto = cand[por_nodo * 2 // 3:]
                cand = top + list(rng.choice(resto, por_nodo - len(top), replace=False))
            for b in cand:
                pares.add((min(a, b), max(a, b)))
        if self.pos_t is not None:
            inv_t = np.argsort(self.pos_t)
            for p in range(self.n):
                for d in range(1, VECINOS_TIEMPO + 1):
                    if p + d < self.n:
                        a, b = int(inv_t[p]), int(inv_t[p + d])
                        pares.add((min(a, b), max(a, b)))
        return sorted(pares)

    def agujas(self, pares):
        """Matriz (len(pares) x 15): las 12 agujas + 3 de contexto, todas en 0..1."""
        F = np.zeros((len(pares), len(NOMBRES_TODAS)), dtype=np.float32)
        l300 = math.log1p(300.0)
        n1 = max(self.n - 1, 2)
        for k, (a, b) in enumerate(pares):
            sa, sb = self.sets[a], self.sets[b]
            com = sa & sb
            r = np.array([self.idf_n[j] for j in com], dtype=np.float32) if com else None
            ia = float(sum(self.idf[j] for j in sa)) or 1e-9
            ib = float(sum(self.idf[j] for j in sb)) or 1e-9
            ic = float(sum(self.idf[j] for j in com))
            peor = max(int(self.rango[a, b]), int(self.rango[b, a]))
            if self.pos_t is not None and self.fiab_episodio > 0:
                ep = math.exp(-abs(int(self.pos_t[a]) - int(self.pos_t[b])) / VENTANA_EPISODIO) * self.fiab_episodio
            else:
                ep = 0.0
            if self.etq is not None and self.fiab_etiquetas > 0 and (self.etq[a] | self.etq[b]):
                et = len(self.etq[a] & self.etq[b]) / len(self.etq[a] | self.etq[b]) * self.fiab_etiquetas
            else:
                et = 0.0
            F[k] = [
                max(0.0, float(self.S[a, b])),
                max(0.0, float(self.Ssem[a, b])),
                float(r.max()) if com else 0.0,
                float(r.mean()) if com else 0.0,
                1.0 - math.exp(-float((r >= 0.6).sum()) / 2.0) if com else 0.0,
                min(1.0, ic / min(ia, ib)),
                max(0.0, 1.0 - math.log1p(peor) / math.log(n1)) if self.S[a, b] > 0 else 0.0,
                len(self.knn[a] & self.knn[b]) / K_VECINOS,
                float(max(self.hub[a], self.hub[b])),
                1.0 if len(com) == 1 else 0.0,
                ep,
                et,
                min(1.0, math.log1p(float(min(self.largo[a], self.largo[b]))) / l300),
                self.fiab_episodio,
                self.fiab_etiquetas,
            ]
        return np.nan_to_num(np.clip(F, 0.0, 1.0), nan=0.0)
