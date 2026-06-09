#!/usr/bin/env python3
"""
Migración única: extrae asociaciones del campo CSV `asociaciones`
de la tabla `largo_plazo` y las inserta en la nueva tabla `sinapsis`.
No modifica ni borra datos existentes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import migrar_desde_csv, init_sinapsis_table, auto_vincular
from core.categorizador import auto_categorizar_existentes

DB_PATH = os.environ.get(
    'BIORAG_PATH',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "MemoryBioRAG_Data", "memory_biorag.db")
)


def migrar_completo(cerebro):
    print("=== Migración BioRAG: Sinapsis + Categorías ===\n")

    init_sinapsis_table(cerebro.cursor)

    csv_count = migrar_desde_csv(cerebro)
    print(f"[1/3] Asociaciones CSV migradas a tabla sinapsis: {csv_count} aristas")

    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis")
    total = cerebro.cursor.fetchone()[0]
    print(f"     Total aristas en sinapsis: {total}")

    auto_count = 0
    cerebro.cursor.execute(
        "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo'"
    )
    for concepto, contenido in cerebro.cursor.fetchall():
        if contenido:
            enlaces = auto_vincular(cerebro, concepto, contenido, umbral=0.35)
            auto_count += len(enlaces)

    print(f"[2/3] Auto-vinculos creados entre nodos existentes: {auto_count}")

    cat_actualizados, cat_total = auto_categorizar_existentes(cerebro)
    print(f"[3/3] Categorías actualizadas: {cat_actualizados}/{cat_total} nodos tenían 'general'")

    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis")
    final = cerebro.cursor.fetchone()[0]
    print(f"\nTotal aristas en sinapsis tras migración: {final}")
    print("\nMigración completada. No se modificaron datos existentes.")


if __name__ == "__main__":
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
    try:
        migrar_completo(cerebro)
    finally:
        cerebro.cerrar_sistema()
