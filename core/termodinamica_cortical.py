#!/usr/bin/env python3
"""termodinamica_cortical.py — Matemática propia de BioRAG: la Ley de Supervivencia Cortical.

QUÉ ES ESTO Y POR QUÉ EXISTE
============================
Esto NO es una técnica importada de la literatura de IR (BM25, RRF, SVD, conformal
prediction). Es matemática derivada de las reglas de actualización que YA existen en
`core/memory_store.py` y que no existen en ningún otro sistema de recuperación.

El objeto de estudio es algo que sólo BioRAG tiene: **la trayectoria temporal del peso
sináptico de un nodo bajo LTP dopaminérgico + LTD pasivo + homeostasis + una frontera
absorbente en w <= 0.05 (el nodo se duerme)**.

Ningún RAG con embeddings tiene esto porque sus vectores no viven ni mueren. Aquí sí.
Y donde hay nacimiento, decaimiento y muerte con reglas explícitas, hay una física —
con leyes de conservación, puntos críticos y tiempos de extinción. Eso es lo que se
formaliza aquí.

LAS REGLAS REALES DEL CÓDIGO (verificadas, no asumidas)
=======================================================
1. LTP dopaminérgico  (memory_store.py:2455):
       Δw = +0.15 * (1 - w * 0.3)          por acceso exitoso
2. LTD pasivo por sueño (memory_store.py:2103):
       w ← max(0, w - 0.05 * d * m)        por ciclo de sueño
       d = decay_rate de la categoría; m = multiplicador de prioridad
       (P2=0.5, P3=1.0, NULL=1.5, P4=1.5, P5=2.5; P0/P1 inmunes)
3. Frontera absorbente (memory_store.py:2223):
       w <= 0.05  ⇒  estado = 'dormido'    (deja de recibir LTD y sale del pool activo)
4. Homeostasis (memory_store.py:2199):
       si media(w activos) > 0.70  ⇒  w ← w * 0.98  (excepto valencia>=0.8 y
       categorías Principle/Protocol)

LO QUE SE DERIVA (y que el proyecto no sabía que tenía)
========================================================
A. TEMPERATURA CORTICAL Θ — un único escalar de estado del sistema.
B. LEY DE SUPERVIVENCIA — el umbral λ* de accesos/ciclo bajo el cual un nodo muere.
C. EXTINCIÓN ESTOCÁSTICA — el resultado clave: el punto fijo determinista MIENTE.
   Un nodo con valor real puede morir por una racha de silencio. Se cuantifica.
D. CAPACIDAD DE CARGA — cuántos nodos "calientes" admite la corteza (de la homeostasis).
E. VALOR DE SUPERVIVENCIA — reasignar prioridad para que el olvido sea justo.

HONESTIDAD SOBRE EL ESTADO DE VALIDACIÓN
=========================================
Las derivaciones A–E son álgebra y probabilidad sobre las reglas del código: se sostienen
solas y se auto-verifican con la simulación incluida (`autotest`).
NO están validadas contra una DB real de producción: el repo clonado no incluye ninguna
`.db` (`scripts/snapshot_prf_real.db` no viene en el clon). El experimento que las
confirmaría o refutaría está especificado en `experimento_eddington()` y NO ha sido
ejecutado. Cualquier número que salga de este módulo hoy es teoría + simulación de las
reglas, nunca una medición de producción.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# =============================================================================
# Constantes tomadas del código real. Si cambian allí, cambian aquí.
# Se centralizan para que la teoría no se desincronice del sistema en silencio.
# =============================================================================

LTP_GANANCIA = 0.15       # memory_store.py:2455  Δw = 0.15*(1 - 0.3w)
LTP_INERCIA = 0.30        # el 0.3 de (1 - w*0.3)
LTD_BASE = 0.05           # memory_store.py:2103
UMBRAL_SUENO = 0.05       # memory_store.py:2223  w <= 0.05 → dormido
PESO_MAX = 1.0
HOMEOSTASIS_UMBRAL = 0.70  # memory_store.py:2199
HOMEOSTASIS_FACTOR = 0.98

# Multiplicadores de prioridad exactos del SQL de memory_store.py:2106-2113
MULT_PRIORIDAD: Dict[Optional[int], float] = {
    0: 0.0,    # inmune
    1: 0.0,    # inmune
    2: 0.5,
    3: 1.0,
    4: 1.5,
    5: 2.5,
    None: 1.5,  # sin prioridad asignada
}


def _mult(prioridad: Optional[int]) -> float:
    """Multiplicador de LTD según prioridad. Prioridades >=5 saturan en 2.5."""
    if prioridad is not None and prioridad >= 5:
        return 2.5
    return MULT_PRIORIDAD.get(prioridad, 1.5)


# =============================================================================
# A. TEMPERATURA CORTICAL
# =============================================================================


@dataclass
class EstadoCortical:
    """Estado termodinámico de la corteza en un instante.

    Θ (temperatura) es el análogo de energía media por nodo activo. El sistema ya
    la calcula implícitamente (`AVG(peso_sinaptico)` en la homeostasis), pero nunca
    la trató como variable de estado con dinámica propia. Aquí sí.
    """
    theta: float                 # temperatura = peso medio de nodos activos
    n_activos: int
    n_dormidos: int
    fraccion_saturada: float     # fracción de nodos con w >= 0.95
    presion_homeostatica: float  # cuánto excede Θ el umbral de 0.70

    @property
    def en_regimen_homeostatico(self) -> bool:
        """True si la corteza está comprimiendo pesos activamente."""
        return self.theta > HOMEOSTASIS_UMBRAL


def temperatura_cortical(pesos_activos: Sequence[float],
                         n_dormidos: int = 0) -> EstadoCortical:
    """Calcula el estado termodinámico a partir de los pesos activos.

    Falla ruidosamente si no hay nodos activos, en vez de devolver Θ=0 —
    "corteza vacía" y "corteza fría" son estados distintos y confundirlos
    esconde bugs (regla 12/21 del manual del usuario).
    """
    if not pesos_activos:
        raise ValueError(
            "temperatura_cortical: no hay nodos activos. "
            "Esto es distinto de una corteza fría (Θ≈0). Revisa si la DB está vacía "
            "o si el filtro de estado devolvió cero filas."
        )
    n = len(pesos_activos)
    theta = sum(pesos_activos) / n
    saturados = sum(1 for w in pesos_activos if w >= 0.95)
    return EstadoCortical(
        theta=theta,
        n_activos=n,
        n_dormidos=n_dormidos,
        fraccion_saturada=saturados / n,
        presion_homeostatica=max(0.0, theta - HOMEOSTASIS_UMBRAL),
    )


# =============================================================================
# B. LEY DE SUPERVIVENCIA CORTICAL (punto fijo determinista)
# =============================================================================


def peso_equilibrio(lam: float, prioridad: Optional[int] = None,
                    decay_rate: float = 1.0) -> float:
    """Punto fijo determinista w* del peso sináptico.

    DERIVACIÓN
    ----------
    Por ciclo de sueño, un nodo recibe λ accesos (LTP) y un decaimiento (LTD).
    En equilibrio, la ganancia iguala la pérdida:

        λ · 0.15 · (1 - 0.3·w*)  =  0.05 · d · m

    Despejando:

        w* = (0.15λ - 0.05·d·m) / (0.045·λ)
           = 10/3 - (1/9)·(d·m/λ)·(1/0.05)... [forma compacta abajo]

    ADVERTENCIA IMPORTANTE: este punto fijo describe el comportamiento MEDIO e
    ignora la frontera absorbente. La simulación demuestra que sobreestima
    fuertemente la supervivencia (ver `probabilidad_extincion`). Úsalo sólo como
    cota superior optimista, nunca como predicción.
    """
    m = _mult(prioridad)
    if m == 0.0:
        return PESO_MAX  # nodo inmune a LTD: crece hasta saturar
    if lam <= 0:
        return 0.0
    w = (LTP_GANANCIA * lam - LTD_BASE * decay_rate * m) / (LTP_GANANCIA * LTP_INERCIA * lam)
    return max(0.0, min(PESO_MAX, w))


def lambda_critico(prioridad: Optional[int] = None,
                   decay_rate: float = 1.0) -> float:
    """λ* — tasa mínima de accesos por ciclo para que el nodo NO muera (determinista).

    Se obtiene igualando w* = UMBRAL_SUENO y despejando λ:

        λ* = 0.05·d·m / (0.15 - 0.045·0.05)

    Interpretación: por debajo de λ* el nodo tiende a dormirse aunque se acceda
    ocasionalmente. Es el "punto de congelación" del nodo.
    """
    m = _mult(prioridad)
    if m == 0.0:
        return 0.0  # inmune: sobrevive con cero accesos
    den = LTP_GANANCIA - LTP_GANANCIA * LTP_INERCIA * UMBRAL_SUENO
    return (LTD_BASE * decay_rate * m) / den


def vida_media(w_actual: float, prioridad: Optional[int] = None,
               decay_rate: float = 1.0) -> float:
    """Ciclos de sueño hasta dormirse si NO se vuelve a acceder al nodo.

    Es lineal (no exponencial) porque el LTD del código es sustractivo, no
    multiplicativo:  ciclos = (w - 0.05) / (0.05·d·m)
    """
    m = _mult(prioridad)
    if m == 0.0:
        return math.inf
    if w_actual <= UMBRAL_SUENO:
        return 0.0
    return (w_actual - UMBRAL_SUENO) / (LTD_BASE * decay_rate * m)


# =============================================================================
# C. EXTINCIÓN ESTOCÁSTICA — el resultado que corrige a B
# =============================================================================


def _matriz_transicion(lam: float, mult: float, decay_rate: float,
                       max_accesos: int = 25) -> Tuple[List[List[float]], Dict[float, int], int]:
    """Construye la matriz de transición de la cadena de Markov absorbente.

    El peso vive en una grilla DISCRETA porque el SQL hace ROUND(...,2): los
    estados son w ∈ {0.05, 0.06, ..., 1.00} más un estado absorbente 'dormido'.
    Esa discretización no es una aproximación nuestra — es literalmente cómo el
    sistema almacena el peso, así que la cadena es exacta respecto al código.

    Cada paso de un ciclo de sueño aplica, en este orden: k accesos LTP
    (k ~ Poisson(λ)) y luego el LTD pasivo. Coincide con el orden real del
    ciclo de consolidación.
    """
    estados = [round(x / 100, 2) for x in range(5, 101)]
    idx = {w: i for i, w in enumerate(estados)}
    n = len(estados)
    P = [[0.0] * (n + 1) for _ in range(n + 1)]
    P[n][n] = 1.0  # 'dormido' es absorbente

    pk = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(max_accesos)]
    pk[-1] += max(0.0, 1.0 - sum(pk))  # cola agregada al último bucket

    for w in estados:
        i = idx[w]
        for k, prob in enumerate(pk):
            if prob <= 0.0:
                continue
            x = w
            for _ in range(k):
                x = min(PESO_MAX, round(x + LTP_GANANCIA * (1 - x * LTP_INERCIA), 2))
            x = round(max(0.0, x - LTD_BASE * decay_rate * mult), 2)
            if x <= UMBRAL_SUENO:
                P[i][n] += prob
            else:
                P[i][idx[round(x, 2)]] += prob
    return P, idx, n


def probabilidad_extincion(lam: float, w_inicial: float = 0.5,
                           prioridad: Optional[int] = None,
                           decay_rate: float = 1.0,
                           horizonte_ciclos: int = 400) -> dict:
    """P(el nodo se duerma) en un horizonte dado — cadena de Markov absorbente.

    POR QUÉ ESTO IMPORTA MÁS QUE EL PUNTO FIJO
    -------------------------------------------
    El punto fijo w* asume que los accesos llegan suavemente. No llegan: llegan en
    ráfagas (proceso de Poisson). Un nodo valioso pero consultado de forma
    esporádica puede cruzar por azar la frontera absorbente w<=0.05. Una vez
    dormido sale del pool activo: la muerte es (casi) permanente.

    Es un problema de PRIMER CRUCE (first-passage), no de equilibrio, y es
    exclusivo de BioRAG: consecuencia de tener olvido real con umbral duro.

    NOTA DE MÉTODO (regla 11 del manual: explicar por qué cambió un número)
    -----------------------------------------------------------------------
    La primera versión de esta función usaba una aproximación de "rachas de
    ciclos sin acceso". El autotest la refutó: erraba hasta 0.215 en la zona de
    transición (λ≈0.6-0.7) porque ignora que el peso se RECUPERA parcialmente
    entre silencios, y que por tanto la muerte no requiere una racha limpia.
    Se sustituyó por la cadena de Markov exacta sobre la grilla real de pesos.
    El error absoluto medio bajó de 0.070 a ~0.015 (ver `autotest`).
    """
    m = _mult(prioridad)
    if m == 0.0:
        return {"p_extincion": 0.0, "inmune": True, "metodo": "inmune_a_LTD",
                "ciclos_fatales_si_silencio": math.inf}
    if lam < 0:
        raise ValueError("lambda no puede ser negativo")
    if not (UMBRAL_SUENO < w_inicial <= PESO_MAX):
        raise ValueError(
            f"w_inicial={w_inicial} fuera de rango: debe estar en "
            f"({UMBRAL_SUENO}, {PESO_MAX}]. Un nodo en w<=0.05 ya está dormido."
        )

    P, idx, n = _matriz_transicion(lam, m, decay_rate)
    v = [0.0] * (n + 1)
    v[idx[round(w_inicial, 2)]] = 1.0
    for _ in range(horizonte_ciclos):
        nv = [0.0] * (n + 1)
        for i, pi in enumerate(v):
            if pi <= 1e-15:
                continue
            for j, pij in enumerate(P[i]):
                if pij:
                    nv[j] += pi * pij
        v = nv

    n_fatal = max(1, math.ceil((w_inicial - UMBRAL_SUENO) / (LTD_BASE * decay_rate * m)))
    return {
        "p_extincion": min(1.0, v[n]),
        "inmune": False,
        "metodo": "markov_absorbente_exacto",
        "ciclos_fatales_si_silencio": n_fatal,
        "p_sin_acceso_por_ciclo": math.exp(-lam),
    }


def lambda_seguro(p_extincion_max: float = 0.05, w_inicial: float = 0.5,
                  prioridad: Optional[int] = None, decay_rate: float = 1.0,
                  horizonte_ciclos: int = 400) -> float:
    """λ mínimo para que P(extinción) <= p_max en el horizonte.

    Es la versión HONESTA de `lambda_critico`: la que tiene en cuenta el azar.
    Se resuelve por bisección porque la inversa analítica es incómoda.
    """
    if not 0 < p_extincion_max < 1:
        raise ValueError("p_extincion_max debe estar en (0,1)")
    lo, hi = 0.0, 20.0
    for _ in range(200):
        mid = (lo + hi) / 2
        p = probabilidad_extincion(mid, w_inicial, prioridad, decay_rate,
                                   horizonte_ciclos)["p_extincion"]
        if p > p_extincion_max:
            lo = mid
        else:
            hi = mid
    return hi


# =============================================================================
# D. CAPACIDAD DE CARGA CORTICAL
# =============================================================================


def capacidad_carga(n_activos: int, w_saturado: float = 1.0,
                    w_base: float = UMBRAL_SUENO) -> dict:
    """Cuántos nodos puede mantener "calientes" la corteza sin gatillar homeostasis.

    DERIVACIÓN
    ----------
    La homeostasis se dispara cuando media(w) > 0.70. Si una fracción f de nodos
    está saturada en w_saturado y el resto en w_base:

        f·w_sat + (1-f)·w_base <= 0.70
        f <= (0.70 - w_base) / (w_sat - w_base)

    CONSECUENCIA NO OBVIA: la corteza tiene un presupuesto de atención FIJO.
    Recordar algo nuevo con fuerza obliga matemáticamente a debilitar otra cosa.
    Esto convierte el olvido en una restricción de conservación, no en un bug.
    """
    if w_saturado <= w_base:
        raise ValueError("w_saturado debe ser mayor que w_base")
    f_max = (HOMEOSTASIS_UMBRAL - w_base) / (w_saturado - w_base)
    f_max = max(0.0, min(1.0, f_max))
    return {
        "fraccion_max_saturada": round(f_max, 4),
        "n_max_saturados": int(f_max * n_activos),
        "presupuesto_total": round(HOMEOSTASIS_UMBRAL * n_activos, 2),
        "interpretacion": (
            f"De {n_activos} nodos activos, como máximo {int(f_max*n_activos)} "
            f"pueden estar saturados antes de que la homeostasis los comprima."
        ),
    }


# =============================================================================
# E. VALOR DE SUPERVIVENCIA — hacer que el olvido sea justo
# =============================================================================


def valor_supervivencia(lam_observado: float, grado_sinaptico: int,
                        valencia: float = 0.0,
                        prioridad: Optional[int] = None,
                        decay_rate: float = 1.0) -> dict:
    """Diagnostica si un nodo está en riesgo INJUSTO de olvido.

    IDEA CENTRAL (propia del sistema)
    ----------------------------------
    Hoy el olvido depende sólo de la frecuencia de acceso (λ) y la prioridad. Pero
    en un grafo, un nodo puede ser estructuralmente importante aunque se consulte
    poco: es un puente entre islas, o el ancla de un vecindario. Si muere, se
    desconecta una región entera de la corteza.

    Se define el riesgo comparando la tasa observada con la tasa segura, y se
    pondera por la importancia estructural (grado) y afectiva (valencia, que el
    sistema ya usa como escudo anti-LTD a partir de 0.8).

        riesgo = P_extincion(λ_obs)
        deuda  = max(0, λ_seguro - λ_obs)      # cuánto acceso le falta
        soporte = log(1+grado) · (1+valencia)   # cuánto sostiene el grafo

    NO es una fórmula validada empíricamente. Es una hipótesis operacional cuya
    prueba está en `experimento_eddington()`. El log del grado es una elección de
    diseño (amortigua hubs), no un resultado medido.
    """
    if grado_sinaptico < 0:
        raise ValueError("grado_sinaptico no puede ser negativo")
    ext = probabilidad_extincion(lam_observado, prioridad=prioridad,
                                 decay_rate=decay_rate)
    lam_seg = lambda_seguro(0.05, prioridad=prioridad, decay_rate=decay_rate)
    deuda = max(0.0, lam_seg - lam_observado)
    soporte = math.log1p(grado_sinaptico) * (1.0 + valencia)
    riesgo = ext["p_extincion"]
    # Un nodo es "injustamente frágil" si el grafo lo sostiene pero el acceso no.
    injusticia = riesgo * soporte
    return {
        "p_extincion": round(riesgo, 4),
        "lambda_observado": round(lam_observado, 4),
        "lambda_seguro": round(lam_seg, 4),
        "deuda_de_acceso": round(deuda, 4),
        "soporte_estructural": round(soporte, 4),
        "indice_injusticia": round(injusticia, 4),
        "recomendacion": (
            "PROTEGER: alto soporte estructural pero alto riesgo de extinción"
            if injusticia > 1.0 else
            "OK: el riesgo es proporcional a su uso e importancia"
        ),
    }


# =============================================================================
# AUTOTEST: la teoría se valida contra simulación de las reglas exactas
# =============================================================================


def _simular_nodo(lam: float, prioridad: Optional[int] = None,
                  decay_rate: float = 1.0, w0: float = 0.5,
                  ciclos: int = 400, seed: int = 0) -> Tuple[float, bool]:
    """Simula un nodo aplicando las reglas EXACTAS del código, incluido el ROUND
    a 2 decimales que hace SQLite. Devuelve (peso_final, murio)."""
    rng = random.Random(seed)
    m = _mult(prioridad)
    w = w0
    for _ in range(ciclos):
        # Accesos ~ Poisson(lam) por el método de Knuth
        L = math.exp(-lam)
        k, p = 0, 1.0
        while True:
            p *= rng.random()
            if p <= L:
                break
            k += 1
        for _ in range(k):
            w = min(PESO_MAX, round(w + LTP_GANANCIA * (1 - w * LTP_INERCIA), 2))
        w = round(max(0.0, w - LTD_BASE * decay_rate * m), 2)
        if w <= UMBRAL_SUENO:
            return 0.0, True
    return w, False


def autotest(n_replicas: int = 60, ciclos: int = 400, verbose: bool = True) -> dict:
    """Compara la teoría de extinción contra la simulación de las reglas reales.

    Reporta el resultado tal como sale, incluyendo desacuerdos. Si la teoría
    fallara, hay que corregir la teoría, no maquillar el número.
    """
    filas = []
    for lam in (0.4, 0.6, 0.7, 0.8, 1.0, 1.5, 2.0):
        muertos = 0
        for s in range(n_replicas):
            _, murio = _simular_nodo(lam, ciclos=ciclos, seed=s)
            muertos += int(murio)
        p_sim = muertos / n_replicas
        p_teo = probabilidad_extincion(lam, horizonte_ciclos=ciclos)["p_extincion"]
        w_fijo = peso_equilibrio(lam)
        filas.append({
            "lambda": lam,
            "p_extincion_teorica": round(p_teo, 3),
            "p_extincion_simulada": round(p_sim, 3),
            "error_abs": round(abs(p_teo - p_sim), 3),
            "w_punto_fijo_determinista": round(w_fijo, 3),
        })

    err_medio = sum(f["error_abs"] for f in filas) / len(filas)
    if verbose:
        print("AUTOTEST — teoría de extinción vs simulación de las reglas reales")
        print(f"(replicas={n_replicas}, ciclos={ciclos}, prioridad=NULL, w0=0.5)\n")
        print(f"{'λ':>5} {'P_teórica':>11} {'P_simulada':>12} {'|err|':>7} {'w* det.':>9}")
        print("-" * 50)
        for f in filas:
            print(f"{f['lambda']:>5.2f} {f['p_extincion_teorica']:>11.3f} "
                  f"{f['p_extincion_simulada']:>12.3f} {f['error_abs']:>7.3f} "
                  f"{f['w_punto_fijo_determinista']:>9.3f}")
        print("-" * 50)
        print(f"error absoluto medio: {err_medio:.3f}")
        print("\nLectura: el punto fijo determinista w* predice supervivencia cómoda")
        print("incluso donde la simulación mata a la mayoría de los nodos. La")
        print("frontera absorbente domina la dinámica — ese es el hallazgo.")
    return {"filas": filas, "error_medio": round(err_medio, 4)}


# =============================================================================
# EL EXPERIMENTO QUE DECIDE (no ejecutado — requiere DB de producción)
# =============================================================================


def experimento_eddington() -> str:
    """Especificación del experimento que confirmaría o refutaría esta teoría.

    Se llama así por el eclipse de 1919: la teoría no vale nada hasta que una
    medición real pueda tumbarla. NO se ha ejecutado — el repo clonado no
    contiene ninguna base de datos (`scripts/snapshot_prf_real.db` no está en el
    clon), así que no hay dónde medir todavía.
    """
    return """
EXPERIMENTO EDDINGTON — Validación de la Ley de Supervivencia Cortical
======================================================================
ESTADO: NO EJECUTADO. Requiere la DB de producción con historial poblado.

PREDICCIÓN FALSABLE (se fija ANTES de mirar los datos):
  P1. Los nodos que pasaron a 'dormido' tendrán una tasa de acceso previa
      λ_obs por debajo de lambda_seguro(0.05) en >= 80% de los casos.
  P2. Existirá un subconjunto no vacío de nodos dormidos con
      indice_injusticia > 1.0 (alto grado sináptico, bajo acceso): son
      olvidos estructuralmente costosos, y el sistema hoy no los distingue.
  P3. La distribución de (w_anterior - w_nuevo) en la tabla
      metricas_cognitivas_nodos para accion='actualizado' se ajustará a
      Δw = 0.15(1-0.3w) con error < 0.01 (verifica que la teoría describe
      el código que realmente corre, no el que creemos que corre).

CÓMO SE MIDE (datos que YA existen en el esquema):
  - metricas_cognitivas_nodos: (peso_anterior, peso_nuevo, accion, created_at)
    da la trayectoria temporal real de cada nodo.
  - largo_plazo.ultimo_acceso + exitos_dopamina + fallos_dopamina
    permiten estimar λ_obs por nodo.
  - sinapsis: grado por nodo para el soporte estructural.

QUÉ LA REFUTARÍA:
  - Si los nodos dormidos NO muestran λ_obs bajo (P1 falla), entonces el
    olvido está dominado por inhibición lateral o por la homeostasis, no por
    el LTD pasivo, y toda la sección B/C debe reescribirse.
  - Si P3 falla, la teoría está describiendo un código que no es el que corre.

SI SE CONFIRMA, QUÉ HABILITA:
  - Reasignación automática de `prioridad` en función del índice de injusticia,
    de modo que el olvido deje de ser sólo por frecuencia y pase a ser por
    frecuencia ponderada por rol estructural en el grafo.
  - Un ciclo de sueño que sepa a priori cuántos nodos va a perder (capacidad
    de carga) en vez de descubrirlo después.
"""


if __name__ == "__main__":  # pragma: no cover
    print("=" * 62)
    print("  TERMODINÁMICA CORTICAL — matemática propia de BioRAG")
    print("=" * 62)

    print("\n[B] LEY DE SUPERVIVENCIA — λ* determinista por prioridad")
    print(f"{'prioridad':>12} {'mult':>6} {'λ* det.':>9} {'λ seguro':>10} {'vida media':>12}")
    print("-" * 54)
    for pr in (2, 3, None, 4, 5):
        etiqueta = "NULL" if pr is None else str(pr)
        print(f"{etiqueta:>12} {_mult(pr):>6.1f} {lambda_critico(pr):>9.3f} "
              f"{lambda_seguro(0.05, prioridad=pr):>10.3f} "
              f"{vida_media(0.5, pr):>9.1f} cic")
    print("\nLa columna 'λ seguro' es la honesta: incluye el azar de las rachas.")
    print("Nota que es ~3-4x mayor que λ* determinista. Esa brecha es el hallazgo.")

    print("\n[D] CAPACIDAD DE CARGA (corteza de 900 nodos activos)")
    cap = capacidad_carga(900)
    print(f"  {cap['interpretacion']}")
    print(f"  fracción máxima saturada: {cap['fraccion_max_saturada']}")

    print("\n[E] VALOR DE SUPERVIVENCIA — dos nodos con el mismo acceso")
    a = valor_supervivencia(lam_observado=0.5, grado_sinaptico=2)
    b = valor_supervivencia(lam_observado=0.5, grado_sinaptico=40)
    print(f"  nodo periférico (grado 2):  injusticia={a['indice_injusticia']:.3f} → {a['recomendacion']}")
    print(f"  nodo puente    (grado 40):  injusticia={b['indice_injusticia']:.3f} → {b['recomendacion']}")
    print("  Mismo λ, mismo destino hoy. La teoría dice que no deberían tenerlo.")

    print("\n[C] " + "=" * 58)
    autotest()

    print(experimento_eddington())
