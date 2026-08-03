"""
Barrido PRIORIDAD MÁXIMA: colisiones del Fallback 1.8 con queries reales cortas.
================================================================================

Dennys pidió (2026-08-02): ticket aparte, prioridad mayor que el HDC — barrer
las queries reales cortas (1-2 palabras) contra el Fallback 1.8 en producción.

Patrón de producción replicado EXACTO (core/similitud_conceptual.py):
  FASE 1 (línea 425-432):
      q_str = " ".join(query_tokens)
      q_vec = generar_vector_sdm(q_str, q_str)          # concepto=contenido, 1 token
  FASE 2 (líneas 228-243):
      n_vec = nodos_sdm[concepto]  (precalculado: generar_vector_sdm(concepto,
              contenido, cat, dims, vecinos) → multi-token, señal rica)
      score_sdm = similitud_sdm(q_vec, n_vec)           # pesa 0.10 en el score final

Dos escenarios de colisión:
  A) Query corta vs query corta: si dos queries REALES distintas producen el
     mismo vector (dist=0, sim=1.0), el Fallback las ve idénticas → señal
     SDM espuria +0.10 a los mismos nodos.
  B) Query corta vs nodo: si una query corta colisiona con el vector de un
     NODO (vectores reales de nodos_sdm), un nodo irrelevante recibe +0.10
     de score SDM → puede cambiar el ranking del Fallback.

Se mide con la MISMA vara que el barrido de 33.411 pares (dist=0, sim=1.0),
y se reporta el peor caso de similitud espuria para dimensionar el impacto.

Uso:  python3 scripts/verificar_fallback18_queries_cortas.py
"""

import sqlite3
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sdm import generar_vector_sdm, distancia_hamming, similitud_sdm

DB = Path(__file__).resolve().parent.parent / "MemoryBioRAG_Data" / "memory_biorag.db"

con = sqlite3.connect(str(DB))
filas = con.execute("SELECT query FROM log_busquedas WHERE query IS NOT NULL AND query != ''").fetchall()
con.close()

queries = sorted({f[0].strip() for f in filas})
cortas = [q for q in queries if len(q.split()) <= 2]
print(f"queries reales totales únicas: {len(queries)}")
print(f"queries cortas (1-2 palabras): {len(cortas)}")
print()

# ── Replicar FASE 1 de producción: vector del query ─────────────────────────
q_vecs = {q: generar_vector_sdm(q, q) for q in cortas}


def reportar(nombre, pares):
    """pares: lista de (item_a, item_b, label_a, label_b)."""
    n = len(pares)
    colisiones = []
    sims = []
    for va, vb, la, lb in pares:
        sim = similitud_sdm(va, vb)
        sims.append(sim)
        if sim == 1.0:
            colisiones.append((la, lb))
    sims.sort()
    pct = len(colisiones) / n * 100 if n else 0.0
    print(f"[{nombre}]")
    print(f"  pares                 : {n}")
    print(f"  colisiones exactas    : {len(colisiones)} ({pct:.4f}%)")
    print(f"  sim media / mediana   : {sum(sims)/len(sims):.4f} / {sims[len(sims)//2]:.4f}")
    print(f"  sim min / max         : {sims[0]:.4f} / {sims[-1]:.4f}")
    if colisiones:
        print("  COLISIONES:")
        for la, lb in colisiones[:25]:
            print(f"    - {la!r} == {lb!r}")
    else:
        print("  (sin colisiones exactas)")
    print()
    return colisiones


print("=" * 70)
print(f"ESCENARIO A — query corta real vs query corta real ({len(cortas)} queries, "
      f"{len(cortas) * (len(cortas) - 1) // 2} pares)")
print("=" * 70)
pares_a = []
qs = list(cortas)
for x, y in combinations(qs, 2):
    pares_a.append((q_vecs[x], q_vecs[y], x, y))
col_a = reportar("A) queries entre sí", pares_a)

# ── Cargar vectores reales de nodos (nodos_sdm de producción) ───────────────
con = sqlite3.connect(str(DB))
nodos = con.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()
con.close()
n_vecs = {c: v for c, v in nodos}
print(f"nodos_sdm en producción: {len(n_vecs)}")
print()

print("=" * 70)
print(f"ESCENARIO B — query corta real vs nodo_sdm ({len(cortas)} queries × "
      f"{len(n_vecs)} nodos = {len(cortas) * len(n_vecs)} pares)")
print("=" * 70)

# Medir similitud query-nodo con los vectores REALES de producción
peor = []  # (sim, query, nodo)
col_b = []
sims_b = []
for q in cortas:
    qv = q_vecs[q]
    for nodo, nv in n_vecs.items():
        sim = similitud_sdm(qv, nv)
        sims_b.append(sim)
        if sim == 1.0:
            col_b.append((q, nodo))
        peor.append((sim, q, nodo))

sims_b.sort()
peor.sort(reverse=True)
n = len(sims_b)
print(f"  pares query×nodo      : {n}")
print(f"  colisiones exactas    : {len(col_b)} ({len(col_b)/n*100:.6f}%)")
print(f"  sim media / mediana   : {sum(sims_b)/len(sims_b):.4f} / {sims_b[n//2]:.4f}")
print(f"  sim min / max         : {sims_b[0]:.4f} / {sims_b[-1]:.4f}")
print()
if col_b:
    print("  COLISIONES query-nodo:")
    for q, nodo in col_b[:30]:
        print(f"    query {q!r} == nodo {nodo!r}")
else:
    print("  (sin colisiones exactas query-nodo)")
print()
print("  TOP-15 similitudes espurias (peor caso de señal SDM falsa):")
for sim, q, nodo in peor[:15]:
    print(f"    sim={sim:.4f}  query={q!r}  nodo={nodo!r}")
print()
print("  Nodos que comparten bits con las queries (cuántos por query):")
# Separación media por query: cuántos nodos quedan a sim > 0.9 (señal casi plena)
for q in cortas:
    qv = q_vecs[q]
    alto = sum(1 for nodo, nv in n_vecs.items() if similitud_sdm(qv, nv) >= 0.90)
    if alto:
        print(f"    query={q!r}: {alto} nodos con sim>=0.90")
print()
print("=== fin ===")
