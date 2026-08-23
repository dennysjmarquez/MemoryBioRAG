#!/usr/bin/env python3
"""
Colador de nodos para backfill de bridges.
Cada llamada entrega el siguiente nodo pendiente.
Después de crear bridges con MCP tools, volver a llamar para el siguiente.
"""
import json, sys, os

COLA = os.path.join(os.path.dirname(__file__), 'cola_bridges.json')

def siguiente():
    with open(COLA, 'r') as f:
        nodos = json.load(f)

    if not nodos:
        print("LISTO — no quedan nodos pendientes.")
        return

    nodo = nodos[0]
    restantes = nodos[1:]

    with open(COLA, 'w') as f:
        json.dump(restantes, f, ensure_ascii=False, indent=2)

    total = len(nodos)
    hechos = total - len(restantes)

    print(f"=== [{hechos}/{total}] {nodo['concepto']} ===")
    print(f"CONTENIDO:\n{nodo['contenido']}")
    print(f"\nSINÓNIMOS: {nodo['sinonimos']}")
    print(f"\n--- Generá 5 bridges y llamá a biorag_aprender con concepto='{nodo['concepto']}' ---")
    print(f"--- Quedan {len(restantes)} nodos pendientes ---")

if __name__ == '__main__':
    siguiente()
