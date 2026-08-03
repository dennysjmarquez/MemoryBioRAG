"""
Verificación Opción 1: colisiones de item_denso_desde_string vs SDM densificado.
==============================================================================

Dennys pidió (2026-08-02): "Verificación, no asunción: después del cambio,
re-correr el mismo barrido de 259 nodos / 33.411 pares que ya armaron, pero
con el hash nuevo — confirmar que las colisiones caen a ~0, no dar por
sentado que 'sha256 es bueno' sin medirlo con la misma vara."

Este script re-corre el barrido EXACTO que encontró el problema:
  - pool: conceptos de los 259 nodos activos de la DB de producción
  - pares: 33.411 (C(259,2))
  - colisión = distancia Hamming == 0 entre items de strings DISTINTOS
  - mide con la MISMA vara (dist=0, no <30%) en tres modos:
      sdm :  densificar(generar_vector_sdm(concepto=x, contenido=x))   [original]
      hash: item_denso_desde_string(x)                                  [Opción 1]

Además reporta la similitud de Hamming entre items de strings distintos
(esperada ~0.50 para direcciones ortogonales) para confirmar que el modo
hash también mejora la separación media, no solo elimina colisiones exactas.

Uso:  python3 scripts/verificar_hdc_hash_no_colisiona.py
"""

import sys
import random
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sdm import generar_vector_sdm, distancia_hamming
from scripts.hdc_binding import densificar, item_denso_desde_string, sim_ham

DB = Path(__file__).resolve().parent.parent / "MemoryBioRAG_Data" / "memory_biorag.db"

con = sqlite3.connect(str(DB))
conceptos = [r[0] for r in con.execute("SELECT concepto FROM largo_plazo WHERE estado='activo'").fetchall()]
con.close()

random.seed(42)
muestra = conceptos
print(f"pool: {len(muestra)} conceptos activos de producción")
print(f"pares: {len(muestra) * (len(muestra) - 1) // 2}\n")


def barrido(nombre, fn):
    """Genera items con fn y cuenta colisiones exactas + similitud media."""
    items = {c: fn(c) for c in muestra}
    colisiones = 0
    sims_par = []
    pares = list(__import__("itertools").combinations(muestra, 2))
    for a, b in pares:
        d = distancia_hamming(items[a], items[b])
        if d == 0:
            colisiones += 1
        sims_par.append(sim_ham(items[a], items[b]))
    sims_par.sort()
    print(f"[{nombre}]")
    print(f"  colisiones exactas (dist=0): {colisiones}/{len(pares)}  ({colisiones/len(pares)*100:.4f}%)")
    print(f"  sim Hamming media      : {sum(sims_par)/len(sims_par):.4f}")
    print(f"  sim mediana            : {sims_par[len(sims_par)//2]:.4f}")
    print(f"  sim min                : {sims_par[0]:.4f}")
    print(f"  sim max                : {sims_par[-1]:.4f}")
    print()


print("=" * 60)
print("Barrido 259 nodos / 33.411 pares (contenido=concepto, patrón HDC)")
print("=" * 60)

barrido("SDM densificado (original)", lambda c: densificar(generar_vector_sdm(concepto=c, contenido=c)))
barrido("hash sha256 directo (Opción 1)", item_denso_desde_string)

print("=== fin ===")
