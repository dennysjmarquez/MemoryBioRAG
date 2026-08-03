"""
Re-medición de rangos Hamming SDM tras el fix de multi-proyección (K seeds).
==============================================================================

El nodo de memoria `sdm_query_by_example_validado_datos_reales` (2026-07-23)
fijó rangos de referencia con el hash VIEJO (ventana contigua md5%512):

  - 8-35 bits  : mismo concepto (nombres distintos)
  - 35-60 bits : relacionados (comparten dimensiones)
  - 60+ bits   : menos relacionados

Con el fix de multi-proyección K (hashes i.i.d. por seed) la DENSIDAD de bits
se preserva pero la ESCALA de distancia cruda cambia (la ventana contigua
generaba solapamiento espurio que acercaba vectores; los hashes independientes
no). Los rangos de referencia quedan obsoletos y deben re-medirse.

Este script es el artefacto reproducible de esa re-medición:
  - usa nodos_sdm de una DB (producción por defecto; --db para copia)
  - separa pares que comparten dimensiones (relacionados) de los que no
  - reporta distribución de distancia Hamming y similitud Jaccard (similitud_sdm)
  - mide recall de pares relacionados por encima de umbrales derivados de los
    no-relacionados (capacidad de ranking del SDM)

Uso:
  python3 scripts/medir_rangos_hamming_sdm.py [--db PATH] [--n 220] [--seed N]

Salida interpretable para actualizar el nodo de memoria con los nuevos rangos.
"""

import sys
import random
import sqlite3
import argparse
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.memory_store import SQLiteMemoryBioRAG
from core.sdm import distancia_hamming, similitud_sdm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).resolve().parent.parent / "MemoryBioRAG_Data" / "memory_biorag.db"))
    ap.add_argument("--n", type=int, default=220, help="nodos a muestrear")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    cerebro = SQLiteMemoryBioRAG(db_path=args.db)
    vecs = {c: v for c, v in cerebro.cursor.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()}
    dims = {}
    for concepto, dim_id in cerebro.cursor.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones").fetchall():
        dims.setdefault(concepto, set()).add(dim_id)
    cerebro.conn.close()

    print(f"DB: {args.db}")
    print(f"nodos_sdm: {len(vecs)} | con dimensiones: {len(dims)}")

    random.seed(args.seed)
    conceptos = [c for c in dims if c in vecs]
    random.shuffle(conceptos)
    concepto_muestra = conceptos[:args.n]
    print(f"muestra: {len(concepto_muestra)} nodos (pares C({len(concepto_muestra)},2)="
          f"{len(concepto_muestra)*(len(concepto_muestra)-1)//2})")

    comp_dist, comp_sim = [], []
    nocomp_dist, nocomp_sim = [], []

    for i in range(len(concepto_muestra)):
        for j in range(i + 1, len(concepto_muestra)):
            a, b = concepto_muestra[i], concepto_muestra[j]
            rel = bool(dims[a] & dims[b])
            d = distancia_hamming(vecs[a], vecs[b])
            s = similitud_sdm(vecs[a], vecs[b])
            if rel:
                comp_dist.append(d); comp_sim.append(s)
            else:
                nocomp_dist.append(d); nocomp_sim.append(s)

    def distrib(l, nom):
        if not l:
            print(f"{nom}: (vacío)")
            return
        l.sort()
        print(f"{nom:22} n={len(l):7} p5={l[len(l)//20]:4} p25={l[len(l)//4]:4} "
              f"p50={statistics.median(l):4} p75={l[3*len(l)//4]:4} p95={l[19*len(l)//20]:4} max={l[-1]:4}")

    print("\n=== DISTANCIA HAMMING (escala cruda) ===")
    distrib(comp_dist, "comp dims (rel)")
    distrib(nocomp_dist, "no comp dims")
    print("\n=== SIMILITUD JACCARD (similitud_sdm) ===")
    distrib([round(s, 3) for s in comp_sim], "comp dims (rel)")
    distrib([round(s, 3) for s in nocomp_sim], "no comp dims")

    def recall_rel(comp, nocomp):
        """% de pares relacionados con sim/1-dist por encima del p90 de los no-rel."""
        if not comp or not nocomp:
            return 0.0
        nocomp_sorted = sorted(nocomp)
        umbral = nocomp_sorted[int(len(nocomp_sorted) * 0.90)]
        return 100.0 * sum(1 for s in comp if s > umbral) / len(comp)

    print(f"\nRecall relacionados sobre p90(no-rel):")
    print(f"  por similitud Jaccard : {recall_rel(comp_sim, nocomp_sim):.1f}%")
    # distancia: menor es más similar → comparar sim=1-d/max
    max_d = max(comp_dist + nocomp_dist) if (comp_dist or nocomp_dist) else 1
    simd = [1 - d / max_d for d in comp_dist]
    simd_no = [1 - d / max_d for d in nocomp_dist]
    print(f"  por distancia normalizada: {recall_rel(simd, simd_no):.1f}%")

    print("\nRangos de referencia NUEVOS (Hammmig comp dims):")
    if comp_dist:
        cd = sorted(comp_dist)
        print(f"  p5-p95: {cd[len(cd)//20]} - {cd[19*len(cd)//20]} bits")
        print(f"  p25-p75: {cd[len(cd)//4]} - {cd[3*len(cd)//4]} bits")


if __name__ == "__main__":
    main()
