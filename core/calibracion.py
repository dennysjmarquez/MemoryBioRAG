#!/usr/bin/env python3
"""calibracion.py — Fusión, calibración y decisión estadística para BioRAG.

Módulo propuesto en docs/REVISION_MATEMATICA.md. Sin dependencias fuera de numpy
(coherente con la filosofía "0 dependencias ML" del proyecto).

Contenido:
  Fusión de señales
    - zscore_por_query        normalización intra-query (arregla escalas incomparables)
    - fusion_rrf              Reciprocal Rank Fusion (Cormack et al. 2009)
    - FusionLogistica         learning-to-rank ligero, 13 pesos aprendidos + s.e.
  Calibración y abstención
    - CalibradorPlatt         score -> probabilidad (Platt 1999)
    - calibracion_isotonica   alternativa no paramétrica (PAVA)
    - UmbralConforme          umbral de abstención con FP <= alpha garantizado
  Ranking
    - mmr                     Maximal Marginal Relevance (Carbonell & Goldstein 1998)
  Grafo
    - dunning_llr             log-likelihood ratio para crear aristas (Dunning 1993)
    - retrofit_normalizado    Faruqui 2015 con normalización por grado y parada por eps
    - energia_dirichlet       diagnóstico de oversmoothing
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

# =============================================================================
# Fusión de señales
# =============================================================================


def zscore_por_query(X: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Normaliza cada columna (señal) dentro de la lista de candidatos de UNA query.

    El score híbrido actual suma BM25/(BM25+3), Jaccard, coseno PPMI y fracciones
    de tokens como si vivieran en la misma escala. No lo están: la varianza de
    cada señal cambia por query y por corpus. Normalizar intra-query hace que los
    pesos signifiquen "importancia relativa" de verdad.

    X: matriz (n_candidatos, n_señales).
    """
    X = np.asarray(X, dtype="float64")
    mu = X.mean(axis=0, keepdims=True)
    sd = X.std(axis=0, keepdims=True)
    return (X - mu) / (sd + eps)


def fusion_rrf(rankings: Sequence[Sequence[str]],
               pesos: Sequence[float] | None = None,
               k: float = 60.0) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum_s w_s / (k + rank_s(d)).

    Invariante a cualquier transformación monótona de cada señal, por lo que
    evita el problema de escalas del score híbrido. k=60 es el valor estándar.

    rankings: lista de listas de conceptos, cada una ordenada de mejor a peor
              por una señal distinta.
    Devuelve lista [(concepto, score)] ordenada descendente.
    """
    if pesos is None:
        pesos = [1.0] * len(rankings)
    if len(pesos) != len(rankings):
        raise ValueError("pesos y rankings deben tener la misma longitud")

    acumulado: Dict[str, float] = {}
    for w, ranking in zip(pesos, rankings):
        for rank, doc in enumerate(ranking, start=1):
            acumulado[doc] = acumulado.get(doc, 0.0) + w / (k + rank)
    return sorted(acumulado.items(), key=lambda kv: -kv[1])


class FusionLogistica:
    """Learning-to-rank puntual: regresión logística sobre señales normalizadas.

    Sustituye los pesos escritos a mano de `_calcular_score_hibrido` por pesos
    estimados de los 921 casos QA, con errores estándar para saber qué señal es
    estadísticamente indistinguible de cero.

    Uso:
        m = FusionLogistica(nombres=["bm25","dim","ppmi",...])
        m.entrenar(X, y)          # X (n, d) normalizada, y in {0,1}
        m.resumen()               # peso +- s.e. por señal
        s = m.puntuar(X_nueva)    # score (log-odds) para rankear
    """

    def __init__(self, nombres: Sequence[str] | None = None, l2: float = 1.0):
        self.nombres = list(nombres) if nombres else None
        self.l2 = float(l2)
        self.pesos_: np.ndarray | None = None
        self.sesgo_: float = 0.0
        self.errores_std_: np.ndarray | None = None

    @staticmethod
    def _sigmoide(z: np.ndarray) -> np.ndarray:
        out = np.empty_like(z)
        pos = z >= 0
        out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
        ez = np.exp(z[~pos])
        out[~pos] = ez / (1.0 + ez)
        return out

    def entrenar(self, X: np.ndarray, y: np.ndarray,
                 iters: int = 300, lr: float = 0.5) -> "FusionLogistica":
        X = np.asarray(X, dtype="float64")
        y = np.asarray(y, dtype="float64").ravel()
        n, d = X.shape
        w = np.zeros(d)
        b = 0.0

        for _ in range(iters):
            p = self._sigmoide(X @ w + b)
            grad_w = X.T @ (p - y) / n + self.l2 * w / n
            grad_b = float((p - y).mean())
            w -= lr * grad_w
            b -= lr * grad_b

        self.pesos_, self.sesgo_ = w, b

        # Errores estándar por la inversa de la Hessiana (información de Fisher).
        p = self._sigmoide(X @ w + b)
        W = p * (1.0 - p)
        H = X.T @ (X * W[:, None]) + self.l2 * np.eye(d)
        try:
            cov = np.linalg.inv(H)
            self.errores_std_ = np.sqrt(np.clip(np.diag(cov), 0.0, None))
        except np.linalg.LinAlgError:
            self.errores_std_ = np.full(d, np.nan)
        return self

    def puntuar(self, X: np.ndarray) -> np.ndarray:
        if self.pesos_ is None:
            raise RuntimeError("entrenar() primero")
        return np.asarray(X, dtype="float64") @ self.pesos_ + self.sesgo_

    def probabilidad(self, X: np.ndarray) -> np.ndarray:
        return self._sigmoide(self.puntuar(X))

    def resumen(self) -> List[dict]:
        """Peso, s.e. y z de cada señal. |z| < 2 => indistinguible de 0."""
        if self.pesos_ is None:
            raise RuntimeError("entrenar() primero")
        se = self.errores_std_ if self.errores_std_ is not None else np.full_like(self.pesos_, np.nan)
        nombres = self.nombres or [f"s{i}" for i in range(len(self.pesos_))]
        filas = []
        for nom, w, s in zip(nombres, self.pesos_, se):
            z = w / s if s and not math.isnan(s) and s > 0 else float("nan")
            filas.append({"senal": nom, "peso": round(float(w), 4),
                          "se": round(float(s), 4), "z": round(float(z), 2),
                          "significativa": bool(abs(z) >= 1.96) if not math.isnan(z) else False})
        return sorted(filas, key=lambda f: -abs(f["peso"]))


# =============================================================================
# Calibración de probabilidad
# =============================================================================


class CalibradorPlatt:
    """Platt scaling: P(correcto | score) = sigmoide(a*score + b).

    Entrena sobre pares (score_top1, acierto) de un conjunto de calibración.
    Convierte el score híbrido (no calibrado, saturado en 1.0) en una
    probabilidad usable para decidir si responder o abstenerse.
    """

    def __init__(self):
        self.a: float = 1.0
        self.b: float = 0.0

    def entrenar(self, scores: Sequence[float], aciertos: Sequence[int],
                 iters: int = 500, lr: float = 0.1) -> "CalibradorPlatt":
        s = np.asarray(scores, dtype="float64")
        y = np.asarray(aciertos, dtype="float64")
        a, b = 1.0, 0.0
        n = max(len(s), 1)
        for _ in range(iters):
            p = 1.0 / (1.0 + np.exp(-(a * s + b)))
            a -= lr * float(((p - y) * s).sum()) / n
            b -= lr * float((p - y).sum()) / n
        self.a, self.b = a, b
        return self

    def probabilidad(self, score: float | np.ndarray) -> float | np.ndarray:
        z = self.a * np.asarray(score, dtype="float64") + self.b
        return 1.0 / (1.0 + np.exp(-z))


def calibracion_isotonica(scores: Sequence[float],
                          aciertos: Sequence[int]) -> Callable[[float], float]:
    """Regresión isotónica por PAVA. Alternativa no paramétrica a Platt.

    Devuelve una función score -> probabilidad, monótona no decreciente.
    Preferible a Platt cuando hay >= 500 puntos de calibración.
    """
    s = np.asarray(scores, dtype="float64")
    y = np.asarray(aciertos, dtype="float64")
    orden = np.argsort(s)
    s, y = s[orden], y[orden]

    # Pool Adjacent Violators
    valores = list(y)
    pesos = [1.0] * len(y)
    i = 0
    while i < len(valores) - 1:
        if valores[i] <= valores[i + 1]:
            i += 1
            continue
        w = pesos[i] + pesos[i + 1]
        v = (valores[i] * pesos[i] + valores[i + 1] * pesos[i + 1]) / w
        valores[i:i + 2] = [v]
        pesos[i:i + 2] = [w]
        if i > 0:
            i -= 1
    # Reexpandir a la longitud original
    fit: List[float] = []
    for v, w in zip(valores, pesos):
        fit.extend([v] * int(round(w)))
    fit_arr = np.asarray(fit[:len(s)], dtype="float64")

    def f(x: float) -> float:
        idx = int(np.searchsorted(s, x, side="right")) - 1
        idx = max(0, min(idx, len(fit_arr) - 1))
        return float(fit_arr[idx])

    return f


class UmbralConforme:
    """Abstención con garantía distribución-libre (predicción conforme split).

    Dado un conjunto de calibración de consultas NEGATIVAS (sin respuesta correcta
    en el corpus), el umbral se fija en el cuantil ceil((n+1)(1-alpha))/n de sus
    scores. Bajo intercambiabilidad, la tasa de falsos positivos en consultas
    negativas futuras es <= alpha. Esto reemplaza el umbral fijo del "filtro de
    honestidad epistémica" por una garantía real.
    """

    def __init__(self, alpha: float = 0.05):
        if not 0 < alpha < 1:
            raise ValueError("alpha debe estar en (0,1)")
        self.alpha = float(alpha)
        self.umbral: float = float("inf")
        self.n_calibracion: int = 0

    def calibrar(self, scores_negativos: Sequence[float]) -> "UmbralConforme":
        s = np.sort(np.asarray(scores_negativos, dtype="float64"))
        n = len(s)
        if n == 0:
            raise ValueError("se necesita al menos un negativo de calibración")
        k = math.ceil((n + 1) * (1.0 - self.alpha))
        self.umbral = float(s[min(k, n) - 1])
        self.n_calibracion = n
        return self

    def responder(self, score: float) -> bool:
        """True = responder; False = abstenerse ('no lo sé')."""
        return float(score) > self.umbral

    def cobertura_minima_detectable(self) -> float:
        """alpha efectivo mínimo alcanzable con n negativos (1/(n+1))."""
        return 1.0 / (self.n_calibracion + 1)


# =============================================================================
# Ranking: diversificación
# =============================================================================


def mmr(candidatos: Sequence[str],
        sim_query: Dict[str, float],
        sim_par: Callable[[str, str], float],
        lam: float = 0.7,
        k: int = 5) -> List[str]:
    """Maximal Marginal Relevance.

    argmax_d [ lam * sim(q,d) - (1-lam) * max_{d' en seleccionados} sim(d,d') ]

    Reduce redundancia en el top-k y en el halo asociativo (Canal 2), donde hoy
    varios nodos casi duplicados ocupan slots distintos.
    """
    seleccionados: List[str] = []
    restantes = list(candidatos)
    while restantes and len(seleccionados) < k:
        mejor, mejor_val = None, -float("inf")
        for d in restantes:
            redundancia = max((sim_par(d, s) for s in seleccionados), default=0.0)
            val = lam * sim_query.get(d, 0.0) - (1.0 - lam) * redundancia
            if val > mejor_val:
                mejor, mejor_val = d, val
        seleccionados.append(mejor)  # type: ignore[arg-type]
        restantes.remove(mejor)      # type: ignore[arg-type]
    return seleccionados


# =============================================================================
# Grafo: creación de aristas y retrofitting
# =============================================================================


def dunning_llr(c_xy: int, c_x: int, c_y: int, N: int) -> float:
    """Log-likelihood ratio de Dunning (1993) para asociación de dos tokens.

    Diseñado para eventos raros en corpus pequeños — el caso exacto de BioRAG
    (~900 nodos). Es mucho más estable que NPMI para decidir si crear una arista
    `pmi_hebbiano`. El estadístico se distribuye ~ chi2 con 1 g.l., así que
    LLR >= 10.83 corresponde a p < 0.001.
    """
    def _xlogx(x: float) -> float:
        return x * math.log(x) if x > 0 else 0.0

    k11 = float(c_xy)
    k12 = float(c_x - c_xy)
    k21 = float(c_y - c_xy)
    k22 = float(N - c_x - c_y + c_xy)
    if min(k11, k12, k21, k22) < 0:
        return 0.0

    # LLR = 2 * (H(celdas) - H(filas) - H(columnas)) en la forma de entropías
    # de la tabla de contingencia 2x2 (Dunning 1993, ec. 16).
    celdas = _xlogx(k11) + _xlogx(k12) + _xlogx(k21) + _xlogx(k22)
    filas = _xlogx(k11 + k12) + _xlogx(k21 + k22)
    cols = _xlogx(k11 + k21) + _xlogx(k12 + k22)
    total = _xlogx(k11 + k12 + k21 + k22)
    return max(0.0, 2.0 * (celdas - filas - cols + total))


def retrofit_normalizado(vectores: Dict[str, np.ndarray],
                         adyacencia: Dict[str, List[Tuple[str, float]]],
                         lam: float = 0.2,
                         tau: float = 5.0,
                         max_iters: int = 20,
                         eps: float = 1e-3) -> Tuple[Dict[str, np.ndarray], dict]:
    """Retrofitting de Faruqui (2015) con dos correcciones:

    1. lam efectivo por nodo: lam_i = lam * deg_i / (deg_i + tau).
       Evita que un hub con 300 vecinos `sinonimo_explicito` arrastre al nodo
       hacia el centroide de la isla igual que un nodo con 2 vecinos buenos
       (oversmoothing).
    2. Parada por cambio relativo en norma de Frobenius en vez de iters fijas.

    Devuelve (vectores_nuevos, metricas).
    """
    nuevos = {k: np.array(v, dtype="float64", copy=True) for k, v in vectores.items()}
    historia = []
    for it in range(max_iters):
        anterior = {k: v.copy() for k, v in nuevos.items()}
        for nodo in nuevos:
            vecinos = [(j, w) for j, w in adyacencia.get(nodo, []) if j in nuevos]
            if not vecinos:
                continue
            grado = len(vecinos)
            lam_i = lam * grado / (grado + tau)
            num = np.zeros_like(nuevos[nodo])
            den = 0.0
            for j, w in vecinos:
                num += w * nuevos[j]
                den += w
            if den <= 0:
                continue
            nuevos[nodo] = (1.0 - lam_i) * vectores[nodo] + lam_i * (num / den)

        num_delta = math.sqrt(sum(float(((nuevos[k] - anterior[k]) ** 2).sum()) for k in nuevos))
        den_delta = math.sqrt(sum(float((anterior[k] ** 2).sum()) for k in nuevos)) + 1e-12
        rel = num_delta / den_delta
        historia.append(round(rel, 6))
        if rel < eps:
            break

    return nuevos, {"iters": it + 1, "cambio_relativo": historia}


def energia_dirichlet(vectores: Dict[str, np.ndarray],
                      adyacencia: Dict[str, List[Tuple[str, float]]]) -> float:
    """E = (1/2) * sum_ij w_ij * ||v_i/sqrt(d_i) - v_j/sqrt(d_j)||^2.

    Diagnóstico de oversmoothing: si la energía cae mucho tras el retrofitting,
    los vectores están colapsando hacia el centroide de cada isla y se está
    perdiendo poder discriminante (sospecha principal sobre `por_tema`).
    """
    grados = {k: max(sum(w for _, w in adyacencia.get(k, [])), 1e-12) for k in vectores}
    total = 0.0
    for i, vecinos in adyacencia.items():
        if i not in vectores:
            continue
        vi = vectores[i] / math.sqrt(grados[i])
        for j, w in vecinos:
            if j not in vectores:
                continue
            vj = vectores[j] / math.sqrt(grados[j])
            total += w * float(((vi - vj) ** 2).sum())
    return total / 2.0


if __name__ == "__main__":  # pragma: no cover
    rng = np.random.default_rng(42)
    print("— demo fusion_rrf —")
    print(fusion_rrf([["a", "b", "c"], ["c", "a", "d"]])[:3])

    print("\n— demo FusionLogistica —")
    X = rng.normal(size=(400, 4))
    y = (X[:, 0] * 1.5 + X[:, 1] * 0.8 + rng.normal(scale=0.5, size=400) > 0).astype(int)
    m = FusionLogistica(nombres=["util_a", "util_b", "ruido_c", "ruido_d"]).entrenar(zscore_por_query(X), y)
    for f in m.resumen():
        print("  ", f)

    print("\n— demo UmbralConforme (alpha=0.05) —")
    neg = rng.uniform(0, 0.6, size=200)
    uc = UmbralConforme(alpha=0.05).calibrar(neg)
    print(f"   umbral={uc.umbral:.4f}  alpha_min_detectable={uc.cobertura_minima_detectable():.4f}")

    print("\n— demo dunning_llr —")
    print("   par fuerte:", round(dunning_llr(30, 40, 45, 1000), 2))
    print("   par débil :", round(dunning_llr(2, 40, 45, 1000), 2))
