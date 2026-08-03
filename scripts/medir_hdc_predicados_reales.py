"""
Medición del binding HDC sobre PREDICADOS REALES del corpus.
=============================================================

Paso 2 de la workstream HDC (instrucción de Dennys): medir la separación de
Hamming específicamente entre pares de predicados que COMPARTEN sujeto o
acción — los casos difíciles homogéneos — no el promedio general.

El corpus real tiene 38 predicados sobre 23 nodos, con 215 pares que
comparten sujeto (Dennys 16, Athena-OEC 14, ...) y 12 pares que comparten
acción. Es exactamente la colisión por homogeneidad temática que el test
sintético (items léxicamente distintos) NO cubre.

Diseño de la medición:
  1. Cada componente (sujeto, accion, objeto) se densifica con el mismo
     pipeline del test sintético (densificar + generar_vector_sdm).
  2. Cada predicado se representa como bundle de 3 binds.
  3. Recuperación: unbind de cada rol + clean-up memory contra el pool de
     items de ese rol. Acierto global por rol.
  4. Medida clave: entre pares de predicados que comparten sujeto (o acción),
     ¿cuánto se separan sus bundles? Si comparten sujeto, sus bundles
     comparten el bind del sujeto → la separación de Hamming de los bundles
     es la medida directa de cuán distinguibles son.
  5. Además: para cada item recuperado, la separación sim(correcto) vs
     max(incorrectos) — si es ~0 es colisión total.

Uso:  python3 scripts/medir_hdc_predicados_reales.py [sdm|hash]
      sdm:  items = densificar(generar_vector_sdm(...))  (modo original, default)
      hash: items = item_denso_desde_string(...)         (Opción 1, sin colisión)
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

print(f"predicados válidos: {len(predicados)}")

# Pool de items por rol (densificados)
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

# =============================================================================
# Bundles por predicado
# =============================================================================

bundles = {}
for concepto, s, a, o in predicados:
    binds = [
        xor(items_densos[("sujeto", s)], roles_vec["sujeto"]),
        xor(items_densos[("accion", a)], roles_vec["accion"]),
        xor(items_densos[("objeto", o)], roles_vec["objeto"]),
    ]
    bundles[(concepto, s, a, o)] = majority_vote(binds)

# =============================================================================
# 1. Acierto global por rol
# =============================================================================

print("\n=== 1. Acierto de recuperación por rol (clean-up memory) ===")

for rol in ("sujeto", "accion", "objeto"):
    aciertos = 0
    separaciones = []
    for concepto, s, a, o in predicados:
        bundle = bundles[(concepto, s, a, o)]
        rec = xor(bundle, roles_vec[rol])
        esperado = {"sujeto": s, "accion": a, "objeto": o}[rol]
        sims = {v: sim_ham(rec, items_densos[(rol, v)]) for v in pools[rol]}
        top1 = max(sims, key=sims.get)
        if top1 == esperado:
            aciertos += 1
        correcto = sims[esperado]
        incorrectos = [v for k, v in sims.items() if k != esperado]
        separaciones.append(correcto - max(incorrectos))
    print(f"  {rol:8s}: acierto {aciertos}/{len(predicados)} ({aciertos/len(predicados):.0%})  "
          f"separación media {sum(separaciones)/len(separaciones):.4f}  "
          f"min {min(separaciones):.4f}  max {max(separaciones):.4f}")

# =============================================================================
# 2. Separación entre pares que COMPARTEN sujeto / acción (colisión homogénea)
# =============================================================================

print("\n=== 2. Separación de bundles en pares que comparten sujeto/acción ===")


def sep_bundles(b1, b2):
    """Similitud de Hamming entre bundles: 1 = indistinguibles, 0 = ortogonales."""
    return sim_ham(b1, b2)


for campo in ("sujeto", "accion"):
    grupos = {}
    for concepto, s, a, o in predicados:
        clave = {"sujeto": s, "accion": a}[campo]
        grupos.setdefault(clave, []).append((concepto, s, a, o))

    pares_mismo = []
    pares_distinto = []
    for clave, miembros in grupos.items():
        if len(miembros) < 2:
            continue
        for i in range(len(miembros)):
            for j in range(i + 1, len(miembros)):
                b1 = bundles[miembros[i]]
                b2 = bundles[miembros[j]]
                pares_mismo.append(sep_bundles(b1, b2))

    # pares de control: mismo rol pero items distintos (mismo sujeto, distinta acción)
    print(f"\n  compartiendo {campo}: {len(pares_mismo)} pares")
    print(f"    sim media entre bundles que comparten {campo}: {sum(pares_mismo)/len(pares_mismo):.4f}")
    print(f"    min: {min(pares_mismo):.4f}  max: {max(pares_mismo):.4f}")

# =============================================================================
# 3. Colisión dura: mismo sujeto Y misma acción (pares casi idénticos)
# =============================================================================

print("\n=== 3. Pares que comparten sujeto Y acción (máxima homogeneidad) ===")

claves = {}
for concepto, s, a, o in predicados:
    clave = (s, a)
    claves.setdefault(clave, []).append((concepto, s, a, o))

duros = {k: v for k, v in claves.items() if len(v) >= 2}
if duros:
    for (s, a), miembros in duros.items():
        for i in range(len(miembros)):
            for j in range(i + 1, len(miembros)):
                b1 = bundles[miembros[i]]
                b2 = bundles[miembros[j]]
                sim_ij = sim_ham(b1, b2)
                o1, o2 = miembros[i][3], miembros[j][3]
                print(f"  ({s}, {a}): '{o1}' vs '{o2}' -> sim bundles {sim_ij:.4f}")
else:
    print("  no hay pares que compartan sujeto y acción a la vez")

# =============================================================================
# 4. Recuperación del OBJETO en los casos homogéneos por sujeto
# =============================================================================

print("\n=== 4. Recuperación del objeto por sujeto compartido ===")

for (s, a), miembros in duros.items():
    for concepto, cs, ca, co in miembros:
        bundle = bundles[(concepto, cs, ca, co)]
        rec = xor(bundle, roles_vec["objeto"])
        sims = {v: sim_ham(rec, items_densos[("objeto", v)]) for v in pools["objeto"]}
        top1 = max(sims, key=sims.get)
        ok = "ok" if top1 == co else "X"
        print(f"  {concepto!r}: objeto '{co}' top1={top1!r} sim={sims[co]:.3f} {ok}")

print("\n=== fin ===")
