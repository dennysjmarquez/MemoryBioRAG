#!/usr/bin/env python3
"""
EXPERIMENTO B — Índice ADN v29 con cromosomas PPMI (inyección no invasiva).
============================================================================
Objetivo: probar que el índice ADN v29 deja de ser degenerado si las
comunidades se derivan del espacio PPMI (kNN mutuo + LPA) en vez del grafo
de sinapsis saturado.

Método: monkeypatch de `core.adn_conceptual.detectar_comunidades` para que
devuelva las comunidades PPMI en el mismo formato esperado por el pipeline
del fork ([{'nodos': [...], 'nombre': str, 'confianza': float}]). El resto
de `reconstruir_indice_nocturno` (centroides, firmas, afinidades, vecinos,
persistencia) se ejecuta SIN tocar el core.

Salida: veredicto de no-degeneración + dump de vecinos de 3 consultas
distintas para comparación cualitativa. Trabaja sobre copia del snapshot.
"""

import argparse
import copy
import shutil
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import core.adn_conceptual as adn
from core.adn_conceptual import ADNConceptualEngine
from core.ppmi_hybrid_search import IndicesBioRAG
from scripts.experimentos.expA_topologia_semantica import (
    cargar_vectores, normalizar, top_k_mutuo, lpa_comunidades,
)

DB_DEFAULT = "snapshots/qa_escape_qcr_20260811.db"


def comunidades_ppmi(db_path, k=15, min_sim=0.3, min_miembros=2):
    """Genera comunidades en el formato exacto que espera reconstruir_indice_nocturno."""
    conceptos, estados, M_raw = cargar_vectores(str(db_path))
    M = normalizar(M_raw)
    aristas = top_k_mutuo(M, k=k, min_sim=min_sim)
    labels = lpa_comunidades(len(M), aristas)
    coms = {}
    for c, lab in zip(conceptos, labels):
        coms.setdefault(lab, []).append(c)
    resultado = []
    for i, (lab, miembros) in enumerate(sorted(coms.items(), key=lambda x: -len(x[1]))):
        if len(miembros) < min_miembros:
            continue
        resultado.append({
            "nodos": sorted(miembros),
            "nombre": f"cromosoma_ppmi_{i:03d}",
            "confianza": min(1.0, len(miembros) / 100.0),
        })
    return resultado, labels


def verificar_no_degeneracion(engine: ADNConceptualEngine):
    """Aplica los criterios 1-4 de no-degeneración sobre el índice cargado."""
    out = []
    nombres = engine.nombres_cromosomas
    out.append(("1. >1 cromosoma útil", len(nombres) >= 2, f"{len(nombres)} cromosomas"))

    # 2) sin cromosoma dominante: distribución de membresías por cromosoma
    if engine.membresias_por_cromosoma:
        total_membresias = sum(len(v) for v in engine.membresias_por_cromosoma.values())
        mayor = max(len(v) for v in engine.membresias_por_cromosoma.values())
        out.append(("2. sin cromosoma dominante", total_membresias and mayor / total_membresias < 0.5,
                    f"mayor={mayor}/{total_membresias} ({mayor / total_membresias:.1%})"))
    else:
        out.append(("2. sin cromosoma dominante", False, "sin membresías"))

    # 3) firmas con varianza real entre nodos
    if engine.firmas:
        vecs = list(engine.firmas.values())
        if len(vecs) >= 2:
            arr = np.array([np.array(list(f.values())) for f in vecs])
            varianza = float(np.var(arr, axis=0).mean())
            out.append(("3. firmas con varianza real", varianza > 1e-4, f"varianza media={varianza:.4f}"))

    # 4) vecinos distintos para consultas distintas
    queries = ["dennys_identidad_personal", "hormiguita_v25_sistema_mantenimiento_seguro_athena_biorag",
               "cv_dennys_secciones_ab_finales_2026", "protocolo_autoinferencia_metacognitiva",
               "hallazgo_adn_degenerado_grafo_sin_modularidad_20260813"]
    sets = []
    for q in queries:
        vec = engine.buscar_por_esencia(q, top_k=5)
        sets.append({v["concepto"] for v in vec})
    if len(sets) >= 3:
        intersecciones = []
        for a in range(len(sets)):
            for b in range(a + 1, len(sets)):
                inter = len(sets[a] & sets[b])
                intersecciones.append(inter)
        prom = float(np.mean(intersecciones))
        out.append(("4. vecinos distintos para consultas distintas", prom < 3, f"intersección media={prom:.1f}/5"))
    return out, queries, sets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--min-sim", type=float, default=0.3)
    ap.add_argument("--min-miembros", type=int, default=2)
    ap.add_argument("--out", default="/tmp/opencode/adn_ppmi_bench.db")
    args = ap.parse_args()

    if Path(args.out).exists():
        Path(args.out).unlink()
    shutil.copy2(args.db, args.out)
    print(f"== Copia de trabajo: {args.out} ==")

    # 1) Generar comunidades PPMI en el formato del fork
    comunidades, labels = comunidades_ppmi(args.db, k=args.k, min_sim=args.min_sim,
                                            min_miembros=args.min_miembros)
    print(f"Comunidades PPMI generadas: {len(comunidades)} (k={args.k}, min_sim={args.min_sim})")
    print(f"Distribución (top 8): {[len(c['nodos']) for c in comunidades[:8]]}...")

    # 2) Monkeypatch: el pipeline del fork usará estas comunidades
    def detectar_comunidades_patch(cerebro, min_densidad=0.3, min_nodos=5):
        return copy.deepcopy(comunidades)

    adn.detectar_comunidades = detectar_comunidades_patch

    # 3) Reconstruir el índice con el pipeline REAL del fork
    resultado = ADNConceptualEngine.reconstruir_indice_nocturno(args.out)
    print(f"\nResultado reconstrucción: {resultado}")

    # 4) Cargar y verificar no-degeneración
    indices = IndicesBioRAG(args.out)
    engine = ADNConceptualEngine(args.out, indices=indices)
    print(f"\nindice_listo={engine.indice_listo}")
    print(f"cromosomas={engine.nombres_cromosomas}")

    checks, queries, sets = verificar_no_degeneracion(engine)
    print("\n--- Criterios de no-degeneración ---")
    todos = True
    for crit, ok, det in checks:
        marca = "PASA" if ok else "FALLA"
        if not ok:
            todos = False
        print(f"  {marca:<6} {crit}: {det}")
    print(f"\n-> VEREDICTO: {'PASA (ADN PPMI no degenerado)' if todos else 'NO PASA'}")

    # 5) Dump cualitativo: vecinos por esencia de consultas distintas
    print("\n--- Vecinos por esencia (top-5) por consulta ---")
    for q, s in zip(queries, sets):
        print(f"\n[{q}]")
        for v in s:
            print(f"   - {v}")

    # 6) Comparación de discriminación: afinidades entre vecinos de consultas distintas
    print("\n--- Intersecciones entre conjuntos de vecinos ---")
    for a in range(len(queries)):
        for b in range(a + 1, len(queries)):
            inter = len(sets[a] & sets[b])
            print(f"  {queries[a][:30]:<32} x {queries[b][:30]:<32} -> {inter}/5")


if __name__ == "__main__":
    main()
