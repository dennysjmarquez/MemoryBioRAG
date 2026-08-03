"""
Margen específico de los 18 pares duros del binding HDC.
=========================================================

Pedido de Dennys (2026-08-02): el desglose de similitud correcto-vs-cada-
confundidor ESPECÍFICAMENTE en los 18 pares duros (predicados que comparten
sujeto Y acción), no el agregado de los 38. El 0.128-0.144 general incluye
20 casos fáciles diluyendo el número; el margen real en los duros podría ser
mucho más chico, y ahí es donde un sistema en producción se rompe primero.

Para cada uno de los 18 casos duros:
  - unbind del objeto contra el bundle del predicado
  - sim contra el objeto CORRECTO
  - sim contra CADA confundidor del mismo grupo (comparten sujeto+acción,
    los candidatos más peligrosos de confundir)
  - margen = sim(correcto) − max(sim(confundidores del grupo))

Criterio de Dennys: si el margen es < 0.05 → ampliar stress test con
predicados sintéticos de sujeto+acción compartidos ANTES de ir al JOIN SQL.

Uso:  python3 scripts/medir_hdc_margen_pares_duros.py [sdm|hash]
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
# Datos reales
# =============================================================================

con = sqlite3.connect(str(DB))
filas = con.execute("SELECT concepto, sujeto, accion, objeto FROM predicados").fetchall()
predicados = []
for concepto, sujeto, accion, objeto in filas:
    if not (sujeto and accion and objeto):
        continue
    predicados.append((concepto, sujeto, accion, objeto))

# Pool de objetos (densificados)
pools = {"sujeto": set(), "accion": set(), "objeto": set()}
for _, s, a, o in predicados:
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

print(f"modo items: {MODO}")

roles_vec = {rol: generar_rol(nombre, seed) for rol, (nombre, seed) in ROLES.items()}

# Bundles por predicado
bundles = {}
for concepto, s, a, o in predicados:
    binds = [
        xor(items_densos[("sujeto", s)], roles_vec["sujeto"]),
        xor(items_densos[("accion", a)], roles_vec["accion"]),
        xor(items_densos[("objeto", o)], roles_vec["objeto"]),
    ]
    bundles[(concepto, s, a, o)] = majority_vote(binds)

# =============================================================================
# Identificar los 18 casos duros: grupos (sujeto, accion) con >= 2 miembros
# =============================================================================

grupos = {}
for concepto, s, a, o in predicados:
    grupos.setdefault((s, a), []).append((concepto, s, a, o))

duros = []  # lista de (concepto, s, a, o, grupo)
for clave, miembros in grupos.items():
    if len(miembros) >= 2:
        for m in miembros:
            duros.append((*m, [x[3] for x in miembros]))

print(f"grupos con sujeto+acción compartidos: {len([g for g in grupos.values() if len(g) >= 2])}")
print(f"casos duros (miembros de esos grupos): {len(duros)}")
print(f"objetos en pool de clean-up: {len(pools['objeto'])}")

# =============================================================================
# Margen por caso duro: correcto vs cada confundidor del mismo grupo
# =============================================================================

print("\n=== Margen correcto-vs-confundidor en los casos duros ===\n")

margenes = []
segundos_globales = []
for concepto, s, a, o, grupo_obj in duros:
    bundle = bundles[(concepto, s, a, o)]
    rec = xor(bundle, roles_vec["objeto"])
    sims = {v: sim_ham(rec, items_densos[("objeto", v)]) for v in pools["objeto"]}

    sim_correcto = sims[o]
    confundidores_grupo = [v for v in grupo_obj if v != o]
    sims_conf = {v: sims[v] for v in confundidores_grupo}
    max_conf_grupo = max(sims_conf.values()) if sims_conf else 0.0
    margen_grupo = sim_correcto - max_conf_grupo

    # segundo mejor de TODO el pool (¿hay confundidor fuera del grupo peor?)
    ranking = sorted(sims.items(), key=lambda kv: kv[1], reverse=True)
    segundo = ranking[1] if len(ranking) > 1 else None

    margenes.append(margen_grupo)
    segundos_globales.append(segundo)

    conf_str = " ".join(f"{v}={sims[v]:.3f}" for v in confundidores_grupo)
    print(f"({s}, {a}) objeto={o!r}")
    print(f"    sim correcto = {sim_correcto:.3f}")
    print(f"    confundidores del grupo: {conf_str}")
    print(f"    margen vs grupo = {margen_grupo:.4f} "
          f"(segundo global: {segundo[0]!r} = {segundo[1]:.3f})")
    print()

# =============================================================================
# Resumen
# =============================================================================

margenes.sort()
print("=== Resumen de márgenes (18 casos duros) ===")
print(f"  min  = {margenes[0]:.4f}")
print(f"  mediana = {margenes[len(margenes)//2]:.4f}")
print(f"  max  = {margenes[-1]:.4f}")
print(f"  media = {sum(margenes)/len(margenes):.4f}")
bajo_05 = [m for m in margenes if m < 0.05]
print(f"  márgenes < 0.05: {len(bajo_05)}/{len(margenes)}")
bajo_08 = [m for m in margenes if m < 0.08]
print(f"  márgenes < 0.08: {len(bajo_08)}/{len(margenes)}")
print(f"  distribución: " + " ".join(f"{m:.3f}" for m in margenes))

print("\n=== fin ===")
