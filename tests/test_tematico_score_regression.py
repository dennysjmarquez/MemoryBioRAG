#!/usr/bin/env python3
"""test_tematico_score_regression.py — Test de regresión para tematico_score.

Este test protege el fix del gate per-candidate en tematico_score:
tematico_score solo debe contribuir cuando hay evidencia léxica real
(bm25_norm > 0.001 o concepto_ratio > 0.001).

Si se pierde el gate, tematico_score satura en queries OOD como
"fresa manzana" y rompe sinonimo recall.
"""

from __future__ import annotations

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

def _check(nombre: str, condicion: bool, detalle: str = "") -> bool:
    """Registra el resultado. Retorna True si pasa, False si falla."""
    if condicion:
        print(f"  OK    {nombre}")
        return True
    else:
        print(f"  FALLO {nombre}")
        if detalle:
            for linea in detalle.strip().splitlines():
                print(f"        {linea}")
        return False


def main() -> int:
    print("=" * 70)
    print("  Test de Regresión: tematico_score gate per-candidate")
    print("=" * 70)

    try:
        from core.memory_store import SQLiteMemoryBioRAG
    except Exception as e:
        print(f"\nERROR importando core.memory_store: {e}")
        return 1

    # _calcular_score_hibrido se invoca sin instancia
    if not hasattr(SQLiteMemoryBioRAG, "_calcular_score_hibrido"):
        print("\nERROR: SQLiteMemoryBioRAG no tiene _calcular_score_hibrido.")
        return 1

    def scorer(**kwargs):
        return SQLiteMemoryBioRAG._calcular_score_hibrido(None, **kwargs)

    # Verificar que se puede invocar
    try:
        scorer(bm25_norm=0.5)
    except Exception as e:
        print(f"\nERROR: no se puede invocar el scorer ({e}).")
        return 1

    todos_ok = True

    print("\nTEST — tematico_score NO debe saturar sin evidencia léxica")
    print("  Caso: query OOD tipo 'fresa manzana' (bm25=0, concepto=0)")
    print("  tematico_score=1.0 (saturado) NO debe mover el score significativamente")

    # Caso 1: tematico_score=1.0 SIN evidencia léxica (bm25=0, concepto=0)
    score_con_tematico = scorer(
        bm25_norm=0.0,
        dim_score=0.0,
        concepto_ratio=0.0,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=1.0,  # saturado
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )

    # Caso 2: tematico_score=0.0 (sin contribución temática)
    score_sin_tematico = scorer(
        bm25_norm=0.0,
        dim_score=0.0,
        concepto_ratio=0.0,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=0.0,
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )

    delta = score_con_tematico - score_sin_tematico
    print(f"        score con tematico=1.0: {score_con_tematico:.4f}")
    print(f"        score con tematico=0.0: {score_sin_tematico:.4f}")
    print(f"        delta (aportación tematico): {delta:.4f}")

    ok = _check(
        "tematico_score no satura sin evidencia léxica (delta < 0.05)",
        delta < 0.05,
        f"tematico_score aporta {delta:.4f} sin evidencia léxica — "
        f"el gate per-candidate no está protegiendo. "
        f"Debería ser < 0.05 (peso 0.08 * 1.0 = 0.08 teórico, "
        f"pero el gate debe bloquearlo cuando bm25=0 y concepto=0)"
    )
    todos_ok = todos_ok and ok

    # Caso 3: CON evidencia léxica (bm25=0.5) — tematico_score DEBE contribuir
    print("\nTEST — tematico_score DEBE contribuir CON evidencia léxica")
    score_con_bm25_y_tematico = scorer(
        bm25_norm=0.5,
        dim_score=0.0,
        concepto_ratio=0.0,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=1.0,
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )
    score_con_bm25_sin_tematico = scorer(
        bm25_norm=0.5,
        dim_score=0.0,
        concepto_ratio=0.0,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=0.0,
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )
    delta_con_bm25 = score_con_bm25_y_tematico - score_con_bm25_sin_tematico
    print(f"        score con bm25=0.5 + tematico=1.0: {score_con_bm25_y_tematico:.4f}")
    print(f"        score con bm25=0.5 + tematico=0.0: {score_con_bm25_sin_tematico:.4f}")
    print(f"        delta (aportación tematico con bm25): {delta_con_bm25:.4f}")

    ok2 = _check(
        "tematico_score CONTRIBUYE con evidencia léxica (delta > 0.02)",
        delta_con_bm25 > 0.02,
        f"tematico_score aporta solo {delta_con_bm25:.4f} con bm25=0.5 — "
        f"debería contribuir (~0.08 * 1.0 = 0.08 teórico)"
    )
    todos_ok = todos_ok and ok2

    # Caso 4: concepto_ratio > 0 pero bm25=0 — también debe permitir tematico
    print("\nTEST — tematico_score DEBE contribuir con concepto_ratio > 0")
    score_con_concepto_y_tematico = scorer(
        bm25_norm=0.0,
        dim_score=0.0,
        concepto_ratio=0.5,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=1.0,
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )
    score_con_concepto_sin_tematico = scorer(
        bm25_norm=0.0,
        dim_score=0.0,
        concepto_ratio=0.5,
        sinonimos_ratio=0.0,
        peso_sinaptico=0.0,
        score_latente=0.0,
        score_cadena=0.0,
        temporal=0.0,
        asoc_count=0,
        grupo_score=0.0,
        tematico_score=0.0,
        pred_score=0.0,
        ppmi_score=0.0,
        hub_match=0.0,
    )
    delta_con_concepto = score_con_concepto_y_tematico - score_con_concepto_sin_tematico
    print(f"        score con concepto=0.5 + tematico=1.0: {score_con_concepto_y_tematico:.4f}")
    print(f"        score con concepto=0.5 + tematico=0.0: {score_con_concepto_sin_tematico:.4f}")
    print(f"        delta (aportación tematico con concepto): {delta_con_concepto:.4f}")

    ok3 = _check(
        "tematico_score CONTRIBUYE con concepto_ratio > 0 (delta > 0.02)",
        delta_con_concepto > 0.02,
        f"tematico_score aporta solo {delta_con_concepto:.4f} con concepto=0.5"
    )
    todos_ok = todos_ok and ok3

    print("\n" + "=" * 70)
    if todos_ok:
        print("RESULTADO: TODOS LOS TESTS PASAN — gate per-candidate FUNCIONA")
        return 0
    else:
        print("RESULTADO: HAY FALLOS — el gate per-candidate NO está protegiendo")
        return 1


if __name__ == "__main__":
    sys.exit(main())