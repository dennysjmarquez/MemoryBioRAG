#!/usr/bin/env python3
"""Migración: clasificar todos los nodos existentes con WordNet lexnames."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.memory_store import SQLiteMemoryBioRAG

cerebro = SQLiteMemoryBioRAG()
cerebro.cursor.execute(
    "SELECT concepto, contenido, sinonimos FROM largo_plazo"
)
nodos = cerebro.cursor.fetchall()
total = len(nodos)
print(f"Clasificando {total} nodos con WordNet lexnames...")
for i, (concepto, contenido, sinonimos) in enumerate(nodos, 1):
    cerebro._clasificar_nodo_wordnet(concepto, contenido or "", sinonimos or "")
    if i % 50 == 0:
        print(f"  [{i}/{total}] clasificados...")
cerebro.conn.commit()

# Stats
cerebro.cursor.execute("SELECT COUNT(DISTINCT concepto) FROM nodo_grupos_semanticos")
n_nodos = cerebro.cursor.fetchone()[0]
cerebro.cursor.execute("SELECT COUNT(*) FROM nodo_grupos_semanticos")
n_relaciones = cerebro.cursor.fetchone()[0]
cerebro.cursor.execute("SELECT COUNT(*) FROM grupos_semanticos")
n_grupos = cerebro.cursor.fetchone()[0]
print(f"\nMigración completa:")
print(f"  {n_nodos} nodos clasificados")
print(f"  {n_relaciones} relaciones palabra→grupo")
print(f"  {n_grupos} grupos semánticos únicos")
