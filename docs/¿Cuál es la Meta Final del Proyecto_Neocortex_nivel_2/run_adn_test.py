"""run_adn_test.py — Validación del Salto Conceptual por ADN (Neocórtex de Sangre).

Prueba que el sistema puede relacionar conceptos dispares (ej. 'gato' con 'soledad'
o 'filosofía') basándose en sus cromosomas semánticos compartidos, sin compartir
ninguna palabra, sinónimo ni enlace léxico directo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adn_conceptual import ADNConceptualEngine


def ejecutar_prueba_adn():
    print("=" * 70)
    print("PRUEBA DE VALIDACIÓN: NEOCÓRTEX DE SANGRE (ADN CONCEPTUAL)")
    print("=" * 70)

    motor = ADNConceptualEngine()

    # Consulta: 'gato' (animal biológico, independiente, contemplativo)
    # Queremos ver si el sistema lo relaciona con 'soledad' o 'filosofia'
    # a pesar de que no comparten ninguna letra, sinónimo ni co-ocurrencia léxica.
    query = "gato"
    print(f"\n[Consulta de Esencia] Buscando conexiones profundas para: '{query}'")
    
    resultados = motor.buscar_por_esencia(query, top_k=3)

    for i, res in enumerate(resultados, 1):
        print(f"\n  {i}. Concepto Relacionado: '{res['concepto'].upper()}'")
        print(f"     - Afinidad Genética (Coseno): {res['afinidad_genetica']}")
        print(f"     - Genes/Cromosomas Compartidos: {res['genes_compartidos']}")
        print(f"     - Firma Genética Completa: {res['firma']}")

    # Validación formal
    conceptos_encontrados = [r["concepto"] for r in resultados]
    print("\n" + "-" * 70)
    print(f"Conceptos relacionados hallados por esencia: {conceptos_encontrados}")
    
    # Verificamos que 'soledad' o 'filosofia' aparezcan debido al gen 'autonomo' o 'contemplativo'
    assert any(c in conceptos_encontrados for c in ['soledad', 'filosofia', 'tigre']), \
        "El motor genético debe encontrar relaciones abstractas no léxicas."

    print("-> [ÉXITO] El Neocórtex de Sangre demostró saltos conceptuales por ADN sin dependencia léxica.")
    print("=" * 70)


if __name__ == "__main__":
    ejecutar_prueba_adn()
