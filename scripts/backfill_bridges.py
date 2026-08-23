#!/usr/bin/env python3
"""
Backfill de bridges para nodos existentes SIN crear nodos duplicados.
Usa crear_hub + agregar_bridges + INSERT concept_hub_nodes directamente.
"""
import json, sys, os, sqlite3

COLA = os.path.join(os.path.dirname(__file__), 'cola_bridges.json')
DB = os.path.join(os.path.dirname(__file__), '..', 'MemoryBioRAG_Data', 'memory_biorag.db')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.concept_hub import crear_hub, agregar_bridges

def agregar(bridges_list):
    """Toma el siguiente nodo de la cola y le agrega bridges SIN crear nodo nuevo."""
    with open(COLA, 'r') as f:
        nodos = json.load(f)

    if not nodos:
        print("LISTO — no quedan nodos pendientes.")
        return

    nodo = nodos[0]
    concepto = nodo['concepto']
    restantes = nodos[1:]

    hub_id = f"hub_{concepto.lower().replace(' ', '_')}"

    conn = sqlite3.connect(DB)
    try:
        # 1. Crear hub
        crear_hub(conn, hub_id, concepto, "Backfill bridges obligatorios")
        # 2. Agregar bridges
        agregar_bridges(conn, hub_id, bridges_list)
        # 3. Enlazar nodo EXISTENTE (no crear nuevo)
        conn.execute(
            'INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto) VALUES (?, ?)',
            (hub_id, concepto)
        )
        conn.commit()
        print(f"OK — hub '{hub_id}' creado con {len(bridges_list)} bridges para '{concepto}'")
    except Exception as e:
        print(f"ERROR — {e}")
        conn.rollback()
    finally:
        conn.close()

    # Guardar progreso
    with open(COLA, 'w') as f:
        json.dump(restantes, f, ensure_ascii=False, indent=2)

    print(f"   Quedan {len(restantes)} nodos pendientes")

def siguiente():
    """Muestra el siguiente nodo pendiente."""
    with open(COLA, 'r') as f:
        nodos = json.load(f)

    if not nodos:
        print("LISTO — no quedan nodos pendientes.")
        return

    nodo = nodos[0]
    total = len(nodos)
    print(f"=== [{800-total+1}/800] {nodo['concepto']} ===")
    print(f"CONTENIDO:\n{nodo['contenido']}")
    print(f"\nSINÓNIMOS: {nodo['sinonimos']}")
    print(f"\n--- Llamá: agregar(['bridge1', 'bridge2', ...]) ---")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'agregar':
        # Uso: python3 backfill_bridges.py agregar '["bridge1","bridge2",...]'
        bridges = json.loads(sys.argv[2])
        agregar(bridges)
    else:
        siguiente()
