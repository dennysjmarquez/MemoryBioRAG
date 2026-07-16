#!/usr/bin/env python3
"""
Backfill de metricas_cognitivas_nodos con datos históricos.

Pobla la tabla puente con los nodos que se pueden recuperar de ciclos anteriores.
Solo captura nodos NUEVOS (creados) que aún existen en largo_plazo.
Nodos eliminados o actualizados no se pueden recuperar históricamente.

Uso:
    python3 backfill_historial.py
    python3 backfill_historial.py --dry-run  # Solo muestra qué se haría
"""

import sqlite3
import sys
import os

DB_PATH = os.environ.get('BIORAG_PATH', os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "MemoryBioRAG_Data", "memory_biorag.db"
))


def backfill(db_path, dry_run=False):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()
    
    # Verificar si la tabla puente existe
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metricas_cognitivas_nodos'")
    if not c.fetchone():
        print("❌ La tabla metricas_cognitivas_nodos no existe.")
        print("   Primero ejecutá BioRAG una vez para que se cree la tabla.")
        conn.close()
        return
    
    # Obtener todos los ciclos con consolidación
    c.execute("""
        SELECT mc.id, mc.timestamp, mc.nodos_consolidados
        FROM metricas_cognitivas mc
        WHERE mc.nodos_consolidados > 0
        ORDER BY mc.timestamp ASC
    """)
    ciclos = c.fetchall()
    
    total_ciclos = len(ciclos)
    ciclos_procesados = 0
    nodos_recuperados = 0
    nodos_perdidos = 0
    
    print(f"📊 Procesando {total_ciclos} ciclos con consolidación...")
    print()
    
    for metrica_id, ts, consolidados in ciclos:
        # Buscar nodos creados cerca de este timestamp (ventana 10 segundos)
        c.execute("""
            SELECT concepto, contenido, peso_sinaptico
            FROM largo_plazo 
            WHERE ABS(creado_en - ?) < 10
        """, (ts,))
        nodos = c.fetchall()
        
        if nodos:
            ciclos_procesados += 1
            for concepto, contenido, peso in nodos:
                nodos_recuperados += 1
                if not dry_run:
                    c.execute("""
                        INSERT INTO metricas_cognitivas_nodos 
                        (metrica_id, concepto, accion, contenido_preview, peso_anterior, peso_nuevo, razon, contexto, anomalo, created_at)
                        VALUES (?, ?, 'nuevo', ?, 0.0, 1.0, 'Backfill: nodo creado en este ciclo', 'backfill=historico', 0, ?)
                    """, (metrica_id, concepto, (contenido or '')[:100], ts))
        else:
            nodos_perdidos += consolidados
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"✅ Backfill completado:")
    print(f"   - Ciclos procesados: {ciclos_procesados}/{total_ciclos}")
    print(f"   - Nodos recuperados: {nodos_recuperados}")
    print(f"   - Nodos perdidos (historia): {nodos_perdidos}")
    print()
    if nodos_perdidos > 0:
        print(f"⚠️  Los {nodos_perdidos} nodos perdidos son nodos que fueron:")
        print(f"   1. ELIMINADOS por evicción (BIORAG_PODAR=true)")
        print(f"   2. O eran ACTUALIZACIONES de nodos existentes (no creaciones)")
        print(f"   En ambos casos, la tabla puente queda vacía para esos ciclos (correcto).")
    print()
    if dry_run:
        print("🔍 Modo dry-run: no se insertaron registros.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    backfill(DB_PATH, dry_run)
