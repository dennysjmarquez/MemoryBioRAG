"""Agujas universales de la neurona asociativa (experimento 11).

Una "aguja" es una señal en escala 0..1 sobre un PAR de recuerdos (A, B). Son
UNIVERSALES: no miran qué palabras hay, sino CÓMO se relacionan los dos
recuerdos dentro de su propia memoria. Por eso las mismas agujas se pueden
calcular en cualquier corpus e idioma (español, inglés, técnico, noticias,
diccionario...).

Cada aguja copia una función del hipocampo (ver README, sección 3):

  parecido        corteza: cuánto se parecen sus palabras (coseno tf-idf)
  semantica       corteza: cuánto se parecen en significado (LSA, 2º orden)
  rareza_max      giro dentado: la pista compartida más rara (una sola pista
                  muy rara ya dice mucho; una palabra común no dice nada)
  rareza_media    giro dentado: qué tan raras son, en promedio, las pistas
  pistas_raras    giro dentado: cuántas pistas raras distintas comparten
  cobertura       CA3: qué parte de lo importante del más corto está en el otro
  mutuo           CA1 / inhibición lateral: ¿A está entre los más cercanos de B
                  Y B entre los de A? (k-ganadores: cada neurona se queda con
                  sus mejores socios)
  vecinos         CA3 (completar patrón): ¿tienen los mismos vecinos cercanos?
  hub             escalado sináptico (homeostasis): ¿alguno de los dos se
                  parece "a todo"? (recuerdo genérico = conexión poco fiable)
  una_sola        Dennys: ¿se tocan por UNA sola palabra?
  corto           ¿alguno es tan corto que hay poca evidencia?

Solo numpy (mismas dependencias que el motor).
"""
import math
import re
import unicodedata

import numpy as np

NOMBRES = ["parecido", "semantica", "rareza_max", "rareza_media", "pistas_raras",
           "cobertura", "mutuo", "vecinos", "hub", "una_sola", "corto"]

_TOK = re.compile(r"[a-z0-9]+")
LARGO_RAIZ = 7          # raíz universal: primeras 7 letras (busqueda/busquedas -> busqued)
DF_MAX = 0.15           # palabras en más del 15 % de los recuerdos = "de relleno" en ESA memoria
DIM_SEM = 100           # dimensiones del espacio semántico (como el PPMI-SVD del motor)
K_VECINOS = 10


def tokens(texto):
    """Raíces universales de un texto (sin lista de palabras vacías de ningún idioma)."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("_", " ").replace("-", " ")
    return [w[:LARGO_RAIZ] for w in _TOK.findall(t) if len(w) >= 3 and not w.isdigit()]


class Memoria:
    """Estadísticas de UNA memoria (corpus) que las agujas necesitan.

    Todo se calcula desde los textos: df/idf de cada raíz, vectores tf-idf,
    espacio semántico (LSA), vecinos cercanos, "hub". Nada viene de afuera.
    """

    def __init__(self, textos, semilla=0):
        self.n = n = len(textos)
        toks = [tokens(t) for t in textos]
        df = {}
        for ts in toks:
            for w in set(ts):
                df[w] = df.get(w, 0) + 1
        tope = max(2, int(DF_MAX * n))
        vocab = sorted(w for w, d in df.items() if 2 <= d <= tope)
        self.idx = {w: i for i, w in enumerate(vocab)}
        self.logn = math.log(n)
        self.idf = np.array([math.log(n / df[w]) for w in vocab], dtype=np.float32)
        self.idf_n = self.idf / self.logn                       # 0..1
        self.sets = [frozenset(self.idx[w] for w in ts if w in self.idx) for ts in toks]
        self.largo = np.array([len(ts) for ts in toks], dtype=np.float32)
        X = np.zeros((n, len(vocab)), dtype=np.float32)
        for i, ts in enumerate(toks):
            for w in ts:
                j = self.idx.get(w)
                if j is not None:
                    X[i, j] += 1.0
        X = np.log1p(X) * self.idf[None, :]
        X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-9)
        self.X = X
        S = X @ X.T                                             # coseno tf-idf
        np.fill_diagonal(S, -1.0)
        self.S = S
        # Espacio semántico (LSA) por la matriz de Gram: G = X X^T = U L U^T
        G = X @ X.T
        L, U = np.linalg.eigh(G.astype(np.float64))
        k = min(DIM_SEM, n - 1)
        L, U = L[::-1][:k], U[:, ::-1][:, :k]
        D = (U * np.sqrt(np.maximum(L, 0))[None, :]).astype(np.float32)
        D /= np.maximum(np.linalg.norm(D, axis=1, keepdims=True), 1e-9)
        Ssem = D @ D.T
        np.fill_diagonal(Ssem, -1.0)
        self.Ssem = Ssem
        # Rango de cada recuerdo en la lista de cercanos del otro (por parecido)
        orden = np.argsort(-S, axis=1)
        self.rango = np.empty_like(orden)
        filas = np.arange(n)[:, None]
        self.rango[filas, orden] = np.arange(n)[None, :]
        # Vecinos cercanos en el espacio semántico
        self.knn = [frozenset(r) for r in np.argsort(-Ssem, axis=1)[:, :K_VECINOS]]
        # Hub: a cuántos recuerdos se parece "algo" (coseno > .1), en percentil 0..1
        cuantos = (S > 0.10).sum(axis=1).astype(np.float64)
        self.hub = (np.argsort(np.argsort(cuantos)) / max(n - 1, 1)).astype(np.float32)

    def candidatos(self, por_nodo=30, rng=None):
        """Los pares que un motor mecánico propondría: comparten al menos una
        raíz (como las reglas de hoy) o son vecinos semánticos (como PPMI).
        Hasta `por_nodo` por recuerdo (MAX_FANOUT del motor = 30): 2/3 los más
        parecidos y 1/3 al azar entre los que solo comparten alguna palabra."""
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
                # como el motor: los más parecidos primero (FTS/PPMI) + algunos al
                # azar de los que solo comparten alguna palabra (reglas mecánicas)
                cand.sort(key=lambda b: -self.S[a, b])
                top = cand[:por_nodo * 2 // 3]
                resto = cand[por_nodo * 2 // 3:]
                cand = top + list(rng.choice(resto, por_nodo - len(top), replace=False))
            for b in cand:
                pares.add((min(a, b), max(a, b)))
        return sorted(pares)

    def agujas(self, pares):
        """Matriz (len(pares) x 11) con las agujas de cada par, todas en 0..1."""
        F = np.zeros((len(pares), len(NOMBRES)), dtype=np.float32)
        n1 = max(self.n - 1, 2)
        for k, (a, b) in enumerate(pares):
            sa, sb = self.sets[a], self.sets[b]
            com = sa & sb
            r = np.array([self.idf_n[j] for j in com], dtype=np.float32) if com else None
            ia = float(sum(self.idf[j] for j in sa)) or 1e-9
            ib = float(sum(self.idf[j] for j in sb)) or 1e-9
            ic = float(sum(self.idf[j] for j in com))
            peor = max(int(self.rango[a, b]), int(self.rango[b, a]))
            F[k] = [
                max(0.0, float(self.S[a, b])),
                max(0.0, float(self.Ssem[a, b])),
                float(r.max()) if com else 0.0,
                float(r.mean()) if com else 0.0,
                1.0 - math.exp(-float((r >= 0.6).sum()) / 2.0) if com else 0.0,
                ic / min(ia, ib),
                1.0 - math.log1p(peor) / math.log(n1),
                len(self.knn[a] & self.knn[b]) / K_VECINOS,
                float(max(self.hub[a], self.hub[b])),
                1.0 if len(com) == 1 else 0.0,
                1.0 - min(1.0, float(min(self.largo[a], self.largo[b])) / 40.0),
            ]
        return np.clip(F, 0.0, 1.0)
