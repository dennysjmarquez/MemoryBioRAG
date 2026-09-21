#!/usr/bin/env python3
"""
Sincronización de Sustantivos Clave Expertos y Concept Hubs Iniciales — BioRAG v32.0.

Aplica de forma reproducible y determinista las cuádruplas jerárquicas formales
(Posición 1: Eje Rector, Posiciones 2-4: Variables de Control Ortogonales)
a los nodos del corpus para garantizar 100% de alineación semántica sin añadir
deuda técnica ni recurrir a aprendizaje estocástico en caliente.

Mapeos Formales Canónicos:
  - 'protocolo_autoinferencia_metacognitiva'    -> 'metacognicion,learning,regla,paso'
  - 'principio_compresion_cognitiva_boveda_5d' -> 'compresion,rector,diagnostico,red'
  - 'mentalidad_biorag_para_agentes'           -> 'mentalidad,rafaga,resultado,agente'
  - 'notebooklm-memory-biorag-project'         -> 'notebooklm,datos,lecciones,postsync'
  - 'biorag_v11_1_detalle_tecnico'             -> 'biorag,activa,largo,archivos'
  - 'dennys-identidad-profunda'                -> 'identidad,dennys,oraculo,manifiesto'
"""

import os
import sys
import sqlite3
import argparse
import unicodedata
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from core.concept_hub import cargar_hubs_iniciales, crear_tablas

# Cuádruplas canónicas jerárquicas (Eje Rector + 3 Variables de Control)
SUSTANTIVOS_EXPERTOS = {
    "protocolo_autoinferencia_metacognitiva": "metacognicion,learning,regla,paso",
    "principio_compresion_cognitiva_boveda_5d": "compresion,rector,diagnostico,red",
    "mentalidad_biorag_para_agentes": "mentalidad,rafaga,resultado,agente",
    "notebooklm-memory-biorag-project": "notebooklm,datos,lecciones,postsync",
    "biorag_v11_1_detalle_tecnico": "biorag,activa,largo,archivos",
    "dennys-identidad-profunda": "identidad,dennys,oraculo,manifiesto",
}


def sincronizar_base_datos(db_path: str, sincronizar_hubs: bool = True) -> dict:
    if not os.path.exists(db_path):
        print(f"[SKIP] Base de datos no encontrada: {db_path}")
        return {"status": "not_found", "db": db_path}

    print(f"\n[INFO] Sincronizando: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    actualizados = 0
    # 1. Aplicar Sustantivos Clave
    for concepto, sustantivos in SUSTANTIVOS_EXPERTOS.items():
        # Verificar si existe el nodo
        cur.execute("SELECT concepto, sustantivos_clave FROM largo_plazo WHERE concepto = ?", (concepto,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?",
                (sustantivos, concepto)
            )
            # Actualizar FTS5 si la tabla existe y tiene columna sustantivos_clave
            try:
                cur.execute(
                    "UPDATE largo_plazo_fts SET sustantivos_clave = ? WHERE concepto = ?",
                    (sustantivos, concepto)
                )
            except Exception:
                pass
            actualizados += 1
            print(f"  ✅ [Nodo Actualizado] '{concepto}' -> '{sustantivos}'")
        else:
            print(f"  ⚠️ [Nodo Ausente] '{concepto}' (no encontrado en largo_plazo)")

    conn.commit()

    # Reconstruir índice FTS5 para consistencia total si existe comando rebuild
    try:
        cur.execute("INSERT INTO largo_plazo_fts(largo_plazo_fts) VALUES('rebuild')")
        conn.commit()
        print("  ✅ [FTS5 Rebuild] Índice FTS5 reconstruido con éxito.")
    except Exception as exc:
        print(f"  ℹ️ [FTS5 Rebuild Skip] {exc}")

    # 2. Cargar Concept Hubs Iniciales si corresponde
    hubs_info = None
    if sincronizar_hubs:
        crear_tablas(conn)
        hubs_info = cargar_hubs_iniciales(conn)
        print(f"  ✅ [Concept Hubs] Sincronizados hubs iniciales (creados/actualizados: {hubs_info.get('hubs_creados')}).")

    conn.close()
    return {
        "status": "ok",
        "db": db_path,
        "nodos_actualizados": actualizados,
        "hubs_info": hubs_info
    }


def main():
    parser = argparse.ArgumentParser(description="Sincronizar Sustantivos Clave Expertos y Concept Hubs")
    parser.add_argument(
        "--target",
        choices=["all", "live", "snapshot", "custom"],
        default="all",
        help="Objetivo de sincronización (default: all -> sincroniza ambas bases)"
    )
    parser.add_argument("--db", default=None, help="Ruta a base personalizada si target=custom")
    parser.add_argument("--no-hubs", action="store_true", help="Omitir sincronización de Concept Hubs")
    args = parser.parse_args()

    live_db = os.path.join(ROOT_DIR, "MemoryBioRAG_Data", "memory_biorag.db")
    snap_db = os.path.join(ROOT_DIR, "snapshots", "qa_escape_qcr_20260811.db")

    sinc_hubs = not args.no_hubs

    if args.target == "live":
        sincronizar_base_datos(live_db, sincronizar_hubs=sinc_hubs)
    elif args.target == "snapshot":
        sincronizar_base_datos(snap_db, sincronizar_hubs=sinc_hubs)
    elif args.target == "custom":
        if not args.db:
            print("[ERROR] Debe especificar --db para target=custom")
            sys.exit(1)
        sincronizar_base_datos(args.db, sincronizar_hubs=sinc_hubs)
    else:  # all
        sincronizar_base_datos(live_db, sincronizar_hubs=sinc_hubs)
        sincronizar_base_datos(snap_db, sincronizar_hubs=sinc_hubs)

    print("\n[SUCCESS] Sincronización completa finalizada.")


if __name__ == "__main__":
    main()
