"""
Stress test sintético: objetos con alto solapamiento léxico bajo mismo
sujeto+acción — patrón de versionado del proyecto.
======================================================================

Pedido de Dennys (2026-08-02): el corpus real de 38 predicados no representa
el peor caso real de este proyecto — conceptos versionados que difieren solo
en un número de versión/sufijo bajo el mismo sujeto y la misma acción
(bug_login_v1 vs bug_login_v2, biorag_v18 vs biorag_v20). Ese es el patrón
de nomenclatura propio del proyecto, no un caso de laboratorio.

Se genera un pool sintético que imita exactamente ese patrón:
  - 3 grupos de sujeto+acción compartidos
  - objetos que comparten casi todo el vocabulario (difieren en el sufijo)
  - pool de clean-up: TODOS los objetos sintéticos + los 38 reales

Se mide el margen correcto-vs-confundidor en cada caso versionado. El
confundidor más peligroso es el hermano de versión (mismo base léxico).

Criterio de Dennys: si el margen aguanta aquí (>> 0.05), hay cobertura real
del peor caso de producción → autoriza comparar contra el JOIN SQL.

Uso:  python3 scripts/test_hdc_stress_versionado.py [sdm|hash]
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sdm import generar_vector_sdm
from scripts.hdc_binding import densificar, generar_rol, xor, majority_vote, sim_ham, item_denso_desde_string

MODO = sys.argv[1] if len(sys.argv) > 1 else "sdm"

DB = Path(__file__).resolve().parent / "snapshot_prf_real.db"
ROLES = {"sujeto": ("__rol_sujeto__", 0), "accion": ("__rol_accion__", 1), "objeto": ("__rol_objeto__", 2)}

# =============================================================================
# Pool sintético con patrón de versionado real del proyecto
# =============================================================================

sinteticos = [
    # (concepto, sujeto, accion, objeto) — mismo sujeto+acción, objetos versionados
    ("syn_test", "Athena-OEC", "corrige", "bug_login_v1"),
    ("syn_test", "Athena-OEC", "corrige", "bug_login_v2"),
    ("syn_test", "Athena-OEC", "corrige", "bug_login_v3"),
    ("syn_test", "auditor_externo", "encuentra", "biorag_v18_baseline_determinista"),
    ("syn_test", "auditor_externo", "encuentra", "biorag_v20_baseline_determinista"),
    ("syn_test", "auditor_externo", "encuentra", "biorag_v22_baseline_determinista"),
    ("syn_test", "Dennys", "aprueba", "hito_mcp_v2"),
    ("syn_test", "Dennys", "aprueba", "hito_mcp_v3"),
    ("syn_test", "Athena-OEC", "implementa", "leccion_versionado_biorag_v1"),
    ("syn_test", "Athena-OEC", "implementa", "leccion_versionado_biorag_v2"),
]

# Pool de clean-up: sintéticos + los 38 reales
con = sqlite3.connect(str(DB))
reales = con.execute("SELECT concepto, sujeto, accion, objeto FROM predicados").fetchall()
reales = [(c, s, a, o) for c, s, a, o in reales if s and a and o]

todos = sinteticos + reales
pools = {"sujeto": set(), "accion": set(), "objeto": set()}
for _, s, a, o in todos:
    pools["sujeto"].add(s)
    pools["accion"].add(a)
    pools["objeto"].add(o)

items_densos = {}
for rol, valores in pools.items():
    for val in valores:
        if MODO == "hash":
            items_densos[(rol, val)] = item_denso_desde_string(val)
        else:
            items_densos[(rol, val)] = densificar(generar_vector_sdm(concepto=val, contenido=val))

roles_vec = {rol: generar_rol(nombre, seed) for rol, (nombre, seed) in ROLES.items()}

bundles = {}
for concepto, s, a, o in todos:
    binds = [
        xor(items_densos[("sujeto", s)], roles_vec["sujeto"]),
        xor(items_densos[("accion", a)], roles_vec["accion"]),
        xor(items_densos[("objeto", o)], roles_vec["objeto"]),
    ]
    bundles[(concepto, s, a, o)] = majority_vote(binds)

# =============================================================================
# Margen por caso versionado: correcto vs hermanos de versión
# =============================================================================

print(f"pool: {len(todos)} predicados ({len(sinteticos)} sintéticos versionados + {len(reales)} reales)")
print(f"objetos en clean-up: {len(pools['objeto'])}")

# agrupar sintéticos por (sujeto, accion)
grupos_syn = {}
for concepto, s, a, o in sinteticos:
    grupos_syn.setdefault((s, a), []).append(o)

print("\n=== Solapamiento base entre hermanos de versión (items densificados) ===")
for (s, a), objs in grupos_syn.items():
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            sim_ij = sim_ham(items_densos[("objeto", objs[i])], items_densos[("objeto", objs[j])])
            print(f"  {objs[i]} vs {objs[j]} = {sim_ij:.4f}")

print("\n=== Margen correcto-vs-confundidor (casos versionados) ===")
margenes = []
aciertos = 0
for concepto, s, a, o in sinteticos:
    bundle = bundles[(concepto, s, a, o)]
    rec = xor(bundle, roles_vec["objeto"])
    sims = {v: sim_ham(rec, items_densos[("objeto", v)]) for v in pools["objeto"]}
    ranking = sorted(sims.items(), key=lambda kv: kv[1], reverse=True)
    top1 = ranking[0][0]
    correcto = sims[o]
    hermanos = [v for v in grupos_syn[(s, a)] if v != o]
    max_hermano = max(sims[v] for v in hermanos) if hermanos else 0.0
    margen = correcto - max_hermano
    margenes.append(margen)
    if top1 == o:
        aciertos += 1

    print(f"({s}, {a}) objeto={o!r}")
    print(f"    sim correcto      = {correcto:.3f}")
    print(f"    sim hermanos      = " + " ".join(f"{v}={sims[v]:.3f}" for v in hermanos))
    print(f"    margen vs hermano = {margen:.4f}  top1={top1!r} {'ok' if top1==o else 'X'}")
    print(f"    confundidor global (top-2 del pool) = {ranking[1][0]!r} = {ranking[1][1]:.3f}")
    print()

margenes.sort()
print("=== Resumen stress test versionado ===")
print(f"  acierto: {aciertos}/{len(sinteticos)}")
print(f"  min  = {margenes[0]:.4f}")
print(f"  mediana = {margenes[len(margenes)//2]:.4f}")
print(f"  max  = {margenes[-1]:.4f}")
print(f"  media = {sum(margenes)/len(margenes):.4f}")
print(f"  márgenes < 0.05: {len([m for m in margenes if m < 0.05])}/{len(margenes)}")
print(f"  márgenes < 0.08: {len([m for m in margenes if m < 0.08])}/{len(margenes)}")
print(f"  distribución: " + " ".join(f"{m:.3f}" for m in margenes))

print("\n=== fin ===")
