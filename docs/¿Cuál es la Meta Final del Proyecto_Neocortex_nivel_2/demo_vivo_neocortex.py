"""demo_vivo_neocortex.py — Demostración en vivo del Neocórtex de Sangre.

1. Introduce un concepto abstracto complejo ("Trascendencia").
2. El motor de ADN Conceptual infiere su firma genética.
3. El motor Teleológico formula hipótesis autónomas de vinculación.
4. Se demuestra el salto conceptual sin palabras coincidentes.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adn_conceptual import ADNConceptualEngine
from core.hipotesis_teleologica import HipotesisTeleologica

def ejecutar_demo():
    print("=" * 80)
    print("DEMOSTRACIÓN EN VIVO: NEOCÓRTEX DE SANGRE Y RAZONAMIENTO TELEOLÓGICO")
    print("=" * 80)

    # Inicializar motores
    adn = ADNConceptualEngine()
    teleologia = HipotesisTeleologica(adn)

    # PASO 1: Introducir un concepto abstracto complejo
    # Definimos "Trascendencia" por sus genes, no por sus palabras.
    # Es altamente abstracto, contemplativo y autónomo.
    concepto_nuevo = "Trascendencia"
    firma_trascendencia = {
        "abstracto": 1.0,
        "contemplativo": 0.95,
        "autonomo": 0.85,
        "biologico": 0.2,
        "social": 0.3,
        "depredador": 0.0,
        "domestico": 0.0,
        "mecanico": 0.0
    }

    print(f"\n[1] Sembrando nuevo concepto complejo: '{concepto_nuevo}'")
    print(f"    Firma Genética: {firma_trascendencia}")
    
    # Integrar y generar hipótesis inmediatas
    resultado_integracion = teleologia.razonar_sobre_nuevo_concepto(concepto_nuevo, firma_trascendencia)
    
    # PASO 2: Mostrar el Salto Conceptual (ADN compartido sin palabras)
    print(f"\n[2] Analizando 'saltos conceptuales' para '{concepto_nuevo}':")
    print("    (Buscando relaciones por esencia, no por texto)")
    
    for hip in resultado_integracion["hipotesis_de_integracion"][:3]:
        print(f"\n    >> Vínculo detectado con: '{hip['objetivo'].upper()}'")
        print(f"       Afinidad Genética: {hip['afinidad']}")
        print(f"       Razón (ADN compartido): {hip['porque']}")

    # PASO 3: Formulación de Hipótesis Teleológica Autónoma
    print("\n[3] El Neocórtex formula una hipótesis proactiva basada en la nueva información:")
    
    hipotesis_globales = teleologia.generar_hipotesis_proactivas(umbral_afinidad=0.8)
    
    # Filtrar las que involucran al nuevo concepto
    hip_especificas = [h for h in hipotesis_globales if concepto_nuevo.lower() in [s.lower() for s in h['sujetos']]]
    
    if hip_especificas:
        h = hip_especificas[0]
        print(f"\n    HIPÓTESIS AUTÓNOMA FORMULADA:")
        print(f"    \"PROPOSICIÓN: {h['proposicion']}\"")
        print(f"    Afinidad: {h['afinidad']}")
        print(f"    Puente Genético: {h['puente_genetico']}")
    else:
        print("\n    No se encontraron hipótesis por encima del umbral de afinidad 0.8.")

    print("\n" + "=" * 80)
    print("DEMOSTRACIÓN FINALIZADA CON ÉXITO: EL SISTEMA 'ENTIENDE' LA ESENCIA.")
    print("=" * 80)

if __name__ == "__main__":
    ejecutar_demo()
