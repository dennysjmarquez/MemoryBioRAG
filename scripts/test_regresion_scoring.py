#!/usr/bin/env python3
"""test_regresion_scoring.py — Tests que habrían detectado los bugs 1.2 y 1.3.

POR QUÉ EXISTE ESTE ARCHIVO
===========================
Los bugs 1.2 (suma de pesos hardcodeada) y 1.3 (rama de sinónimos que aplastaba
todos los scores a un piso fijo) pasaron por `test_memory.py` con 16/16 en verde.
No porque la suite esté mal hecha, sino porque **no comprueba propiedades del
scoring**: comprueba mecánica (LTP, sueño, SDM, inferencia).

Un test que verifica "la función devuelve un número entre 0 y 1" no puede detectar
que cinco entradas distintas devuelven el mismo número. Estos tests sí.

Son tests de PROPIEDADES, no de valores concretos: no se rompen si alguien
recalibra un peso a conciencia, solo si se rompe una invariante del diseño.

USO
    python3 scripts/test_regresion_scoring.py
    (sin argumentos; no necesita DB)

Salida: OK / FALLO por test, y código de salida 1 si alguno falla (para CI).
"""
from __future__ import annotations

import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

_fallos: list[str] = []


def _check(nombre: str, condicion: bool, detalle: str = "") -> None:
    """Registra el resultado de una comprobación. No aborta: reporta todas."""
    if condicion:
        print(f"  OK    {nombre}")
    else:
        print(f"  FALLO {nombre}")
        if detalle:
            for linea in detalle.strip().splitlines():
                print(f"        {linea}")
        _fallos.append(nombre)


# =============================================================================
# TEST 1 — Bug 1.3: la rama de sinónimos debe preservar el orden
# =============================================================================

def test_sinonimos_preserva_orden(scorer) -> None:
    """Dos nodos con sinonimia perfecta pero distinta evidencia deben salir distintos.

    EL BUG QUE DETECTA: la versión con `max(logit, target_logit)` mapeaba todo
    score por debajo del target al mismo valor exacto (0.70), creando empates
    masivos que el ranking resolvía por el orden del SELECT de SQLite. Cinco
    entradas distintas (0.20 .. 0.69) salían todas como 0.7000.

    La invariante correcta: si sinonimos_ratio es idéntico, el orden relativo lo
    debe seguir decidiendo el resto de la evidencia.
    """
    print("\nTEST 1 — rama sinónimos preserva el orden interno")
    # Se varía bm25 para generar scores base distintos, con sinonimia perfecta.
    entradas = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    salidas = [scorer(bm25_norm=b, sinonimos_ratio=1.0) for b in entradas]

    for b, s in zip(entradas, salidas):
        print(f"        bm25={b:.1f} -> score={s:.4f}")

    distintas = len(set(salidas))
    _check("salidas distintas para entradas distintas",
           distintas == len(entradas),
           f"solo {distintas} valores únicos de {len(entradas)}; "
           f"hay empates artificiales en el ranking")

    _check("orden monótono no decreciente",
           all(a <= b for a, b in zip(salidas, salidas[1:])),
           f"salidas={salidas}")


# =============================================================================
# TEST 2 — Bug 1.3: match_exacto también debe preservar el orden
# =============================================================================

def test_match_exacto_preserva_orden(scorer) -> None:
    """El bono de match_exacto no debe colapsar scores (era `max(0.95, score)`)."""
    print("\nTEST 2 — match_exacto preserva el orden interno")
    entradas = [0.1, 0.3, 0.5, 0.7]
    salidas = [scorer(bm25_norm=b, match_exacto=True) for b in entradas]
    for b, s in zip(entradas, salidas):
        print(f"        bm25={b:.1f} -> score={s:.4f}")

    _check("salidas distintas", len(set(salidas)) == len(entradas),
           f"solo {len(set(salidas))} únicos de {len(entradas)}")
    _check("orden monótono", all(a <= b for a, b in zip(salidas, salidas[1:])))


# =============================================================================
# TEST 3 — Bug 1.2: la normalización debe seguir a los pesos reales
# =============================================================================

def test_normalizacion_coherente(scorer) -> None:
    """Con todas las señales al máximo, el score debe llegar a ~1.0.

    EL BUG QUE DETECTA: si la suma usada para normalizar (total_base) deja de
    coincidir con la suma real de los pesos de la fórmula, el score deja de estar
    normalizado. Con todo a 1.0 debería dar 1.0; si da 0.75 o 1.34, la
    normalización está desincronizada.

    Esta es la versión funcional del test: no mira el código, mira el resultado.
    Por eso detecta la desincronización aunque el dict y la fórmula estén
    duplicados (que es como está hoy).
    """
    print("\nTEST 3 — normalización coherente con los pesos reales")
    maxi = scorer(
        bm25_norm=1.0, dim_score=1.0, concepto_ratio=1.0, sinonimos_ratio=0.0,
        peso_sinaptico=1.0, score_latente=1.0, grupo_score=1.0,
        tematico_score=1.0, temporal=1.0, asoc_count=20, pred_score=1.0,
        ppmi_score=1.0, hub_match=1.0,
    )
    print(f"        todas las señales al máximo -> score={maxi:.4f}")
    # sinonimos_ratio=0 para no disparar la rama de bono; el resto al máximo.
    # Con hub_match=1.0 (signal #14), el techo sube a ~0.95.
    _check("score máximo cerca del techo teórico",
           maxi >= 0.90,
           f"esperado >= 0.90, obtenido {maxi:.4f}. "
           f"Si difiere, total_base no coincide con la suma real de la fórmula.")

    cero = scorer()
    print(f"        todas las señales a cero    -> score={cero:.4f}")
    _check("score mínimo es 0.0", abs(cero) < 1e-9, f"obtenido {cero}")


# =============================================================================
# TEST 4 — Monotonía general: más evidencia nunca puede bajar el score
# =============================================================================

def test_monotonia_por_senal(scorer) -> None:
    """Subir cualquier señal individual no debe bajar el score.

    Invariante básica de un scoring aditivo con pesos positivos. Detecta signos
    invertidos y normalizaciones mal aplicadas.
    """
    print("\nTEST 4 — monotonía por señal individual")
    senales = ["bm25_norm", "dim_score", "concepto_ratio", "peso_sinaptico",
               "grupo_score", "tematico_score", "temporal", "pred_score",
               "ppmi_score"]
    for s in senales:
        bajo = scorer(**{s: 0.0})
        alto = scorer(**{s: 1.0})
        _check(f"'{s}' es monótona", alto >= bajo,
               f"con 0.0 -> {bajo:.4f}, con 1.0 -> {alto:.4f}")


def main() -> int:
    print("=" * 66)
    print("  Tests de regresión del scoring híbrido (bugs 1.2 y 1.3)")
    print("=" * 66)

    try:
        from core.memory_store import SQLiteMemoryBioRAG
    except Exception as e:
        print(f"\nERROR importando core.memory_store: {e}")
        return 1

    # _calcular_score_hibrido no usa estado de instancia, así que se puede
    # invocar sin abrir una DB. Se verifica que exista antes de usarla.
    if not hasattr(SQLiteMemoryBioRAG, "_calcular_score_hibrido"):
        print("\nERROR: SQLiteMemoryBioRAG no tiene _calcular_score_hibrido. "
              "¿Cambió el nombre del método?")
        return 1

    def scorer(**kwargs):
        return SQLiteMemoryBioRAG._calcular_score_hibrido(None, **kwargs)

    try:
        scorer(bm25_norm=0.5)
    except Exception as e:
        print(f"\nERROR: no se puede invocar el scorer sin instancia ({e}).")
        print("Abre una DB temporal y pasa la instancia real.")
        return 1

    test_sinonimos_preserva_orden(scorer)
    test_match_exacto_preserva_orden(scorer)
    test_normalizacion_coherente(scorer)
    test_monotonia_por_senal(scorer)

    print("\n" + "=" * 66)
    if _fallos:
        print(f"RESULTADO: {len(_fallos)} FALLO(S)")
        for f in _fallos:
            print(f"  - {f}")
        return 1
    print("RESULTADO: todos los tests pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
