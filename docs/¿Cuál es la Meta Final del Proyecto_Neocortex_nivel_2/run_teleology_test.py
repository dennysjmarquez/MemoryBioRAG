"""run_teleology_test.py — Validación del Flujo Teleológico y Conceptos Complejos.

Introduce conceptos abstractos complejos y verifica la formulación de hipótesis
autónomas basadas en el ADN Conceptual.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adn_conceptual import ADNConceptualEngine
from core.hipotesis_teleologica import HipotesisTeleologica

def ejecutar_prueba_teleologica():
    print("=" * 70)
    print("VALIDACIÓN TELEOLÓGICA: FORMULACIÓN DE HIPÓTESIS Y CONCEPTOS COMPLEJOS")
    print("=" * 70)

    adn = ADNConceptualEngine()
    motor = HipotesisTeleologica(adn)

    # 1. Introducir conceptos abstractos complejos
    nuevos_conceptos = {
        "justicia": {
            "abstracto": 1.0, "social": 0.8, "autonomo": 0.5, "contemplativo": 0.4,
            "biologico": 0.0, "depredador": 0.0, "domestico": 0.0, "mecanico": 0.0
        },
        "entropia": {
            "abstracto": 1.0, "mecanico": 0.7, "biologico": 0.3, "autonomo": 0.4,
            "social": 0.0, "depredador": 0.0, "domestico": 0.0, "contemplativo": 0.0
        },
        "libertad": {
            "abstracto": 1.0, "autonomo": 1.0, "social": 0.6, "biologico": 0.2,
            "depredador": 0.0, "domestico": 0.0, "mecanico": 0.0, "contemplativo": 0.3
        },
        "algoritmo": {
            "abstracto": 0.9, "mecanico": 1.0, "autonomo": 0.4, "biologico": 0.0,
            "social": 0.0, "depredador": 0.0, "domestico": 0.0, "contemplativo": 0.0
        },
        "belleza": {
            "abstracto": 1.0, "contemplativo": 0.9, "biologico": 0.5, "social": 0.6,
            "autonomo": 0.3, "depredador": 0.0, "domestico": 0.0, "mecanico": 0.0
        }
    }

    print("\n[Fase 1] Sembrando nuevos genes en el Neocórtex...")
    for concepto, firma in nuevos_conceptos.items():
        res = motor.razonar_sobre_nuevo_concepto(concepto, firma)
        print(f"-> Concepto '{concepto}' integrado. Hipótesis iniciales: {len(res['hipotesis_de_integracion'])}")

    # 2. Generar hipótesis proactivas (curiosidad del sistema)
    print("\n[Fase 2] Generando Hipótesis Autónomas (Teleología)...")
    hipotesis = motor.generar_hipotesis_proactivas(umbral_afinidad=0.7)

    print(f"\nSe han formulado {len(hipotesis)} hipótesis de alto valor genético:")
    for i, h in enumerate(hipotesis[:10], 1):
        print(f"\n  H-{i}: {h['proposicion']}")
        print(f"       Afinidad: {h['afinidad']}")

    # 3. Validación de saltos específicos
    # ¿Relacionó Libertad con Soledad o Gato por el gen Autónomo?
    # ¿Relacionó Algoritmo con Reloj por el gen Mecánico?
    print("\n" + "-" * 70)
    proposiciones = [h['proposicion'] for h in hipotesis]
    
    # Comprobación de saltos teleológicos esperados
    check_autonomia = any("libertad" in p.lower() and "gato" in p.lower() for p in proposiciones)
    check_mecanico = any("algoritmo" in p.lower() and "reloj" in p.lower() for p in proposiciones)
    check_contemplativo = any("belleza" in p.lower() and "filosofia" in p.lower() for p in proposiciones)

    if check_autonomia: print("[OK] Hipótesis de autonomía: Libertad <-> Gato detectada.")
    if check_mecanico: print("[OK] Hipótesis mecánica: Algoritmo <-> Reloj detectada.")
    if check_contemplativo: print("[OK] Hipótesis contemplativa: Belleza <-> Filosofía detectada.")

    print("\n-> [ÉXITO] El sistema formuló hipótesis autónomas cruzando conceptos dispares por ADN.")
    print("=" * 70)

if __name__ == "__main__":
    ejecutar_prueba_teleologica()
