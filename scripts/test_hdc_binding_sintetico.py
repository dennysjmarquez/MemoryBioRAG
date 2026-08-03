"""
Test sintético del binding HDC (Hyperdimensional Computing) sobre vectores SDM.
================================================================================

Propósito (instrucción aprobada por Dennys):
  Validar que el pipeline HDC — densificar + bind (XOR) + bundle (majority
  vote) + unbind + clean-up memory — permite representar predicados
  (sujeto, accion, objeto) en el espacio de 2048 bits que usa el SDM real,
  y recuperar cada rol.

Patrón (definido con Dennys):
  - Items:   generar_vector_sdm(concepto=..., contenido=...)   (SDM real)
  - Roles:   pseudoaleatorios densos deterministas (hash sha256, ~50%)
  - Densificar: por bit activo del item, un vector denso i.i.d. determinista;
                resultado = majority-vote de esos vectores.
  - Bind:    item_densificado XOR rol
  - Bundle:  voto de mayoría bit a bit (NO encadenar XOR de 3 términos)
  - Unbind:  bundle XOR rol
  - Clean-up: elegir el item conocido más similar (Hamming) al recuperado.

Criterios (por rol):
  - sim(correcto) > max(sim(incorrectos))    (separación)
  - sim(correcto) > 0.7                       (señal fuerte)
  - top1 de clean-up memory == item esperado
Robustez: el test corre sobre N_SEEDS sets de roles y exige que TODOS pasen.

Caso rol ausente: si un rol no participó del bundle, su unbind no debe
producir señal distinguible — la similitud contra el item ausente debe
quedar en el ruido de fondo (~0.5), claramente bajo el umbral de señal 0.7.

Uso:  python3 scripts/test_hdc_binding_sintetico.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sdm import generar_vector_sdm
from scripts.hdc_binding import (densificar, generar_rol, xor, majority_vote,
                                 sim_ham, bind, unbind, recuperar_rol)

N_SEEDS = 5

PASS = 0
FAIL = 0


def check(cond: bool, msg: str):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {msg}")
    else:
        FAIL += 1
        print(f"  X   {msg}")


# =============================================================================
# Vectores base (SDM real)
# =============================================================================

print("=== Vectores base (SDM real, 2048 bits) ===")

items_dispersos = {
    "Dennys": generar_vector_sdm(concepto="Dennys", contenido="persona"),
    "construyo": generar_vector_sdm(concepto="construyo", contenido="accion de crear"),
    "Artisan": generar_vector_sdm(concepto="Artisan", contenido="sistema de gobernanza"),
}
items_densos = {k: densificar(v) for k, v in items_dispersos.items()}

print("  items densificados: " + ", ".join(
    f"{k}={sum(b.bit_count() for b in v)} bits ({sum(b.bit_count() for b in v)/2048:.0%})"
    for k, v in items_densos.items()))

base_ok = all(sim_ham(items_densos[k1], items_densos[k2]) < 0.7
              for k1 in items_densos for k2 in items_densos if k1 < k2)
check(base_ok, "items distintos densificados quedan por debajo de 0.7 de similitud")

roles_nombres = {"sujeto": "__rol_sujeto__", "accion": "__rol_accion__", "objeto": "__rol_objeto__"}
items_map = {"sujeto": "Dennys", "accion": "construyo", "objeto": "Artisan"}

# =============================================================================
# Recuperación por rol, con robustez sobre N_SEEDS sets de roles
# =============================================================================

print(f"\n=== Recuperación del predicado ({N_SEEDS} sets de roles) ===")

for seed in range(N_SEEDS):
    roles = {r: generar_rol(nombre, seed + idx * 10)
             for idx, (r, nombre) in enumerate(roles_nombres.items())}

    binds = [bind(items_densos[items_map[r]], roles[r]) for r in ("sujeto", "accion", "objeto")]
    bundle = majority_vote(binds)

    for r in roles:
        top1, sim_correcto = recuperar_rol(bundle, roles[r], items_densos)
        nombre_esperado = items_map[r]
        separa = sim_correcto > max(sim_ham(unbind(bundle, roles[r]), v)
                                    for n, v in items_densos.items() if n != nombre_esperado)
        print(f"  seed={seed} R_{r:7s} correcto={sim_correcto:.3f} top1={top1!r:10s} "
              f"separacion={'ok' if separa else 'X'} senal={'ok' if sim_correcto > 0.7 else 'X'}")
        check(separa, f"seed={seed} R_{r}: correcto > incorrectos")
        check(sim_correcto > 0.7, f"seed={seed} R_{r}: señal fuerte (>0.7)")
        check(top1 == nombre_esperado, f"seed={seed} R_{r}: clean-up memory top1 correcto")

# =============================================================================
# Robustez a distorsión: bundle de SOLO 2 roles, unbind del ausente
# =============================================================================

print("\n=== Bundle de SOLO 2 roles: el rol ausente no debe recuperarse ===")

roles_1 = {r: generar_rol(nombre, 7 + idx * 10)
           for idx, (r, nombre) in enumerate(roles_nombres.items())}
bundle_2 = majority_vote([
    bind(items_densos["Dennys"], roles_1["sujeto"]),
    bind(items_densos["construyo"], roles_1["accion"]),
])
rec_ausente = unbind(bundle_2, roles_1["objeto"])
sim_ausente = sim_ham(rec_ausente, items_densos["Artisan"])
print(f"  sim(rec_obj_ausente, Artisan) = {sim_ausente:.3f} "
      f"(fondo ~0.5, señal real ~0.75)")
check(sim_ausente < 0.7, "rol ausente del bundle no produce señal distinguible (<0.7)")

# =============================================================================
# Resumen
# =============================================================================

print(f"\n=== Resultado: {PASS} ok, {FAIL} fail ===")
sys.exit(1 if FAIL else 0)
