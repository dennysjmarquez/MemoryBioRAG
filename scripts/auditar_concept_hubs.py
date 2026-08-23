#!/usr/bin/env python3
"""Script de auditoría exhaustiva de la arquitectura Concept Hub en BioRAG."""

import sqlite3
import json
import os
import sys

def auditar_base_datos(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    reporte = {
        "db_path": db_path,
        "filas_por_tabla": {},
        "bridges_huerfanos": [],
        "nodos_relacionados_huerfanos": [],
        "canonical_nodes_inexistentes": [],
        "node_conceptos_inexistentes": [],
        "bridges_repetidos": [],
        "hubs_con_menos_de_5_bridges": [],
        "hubs_sin_5_angulos": [],
        "detalle_hubs": [],
    }

    tablas = [
        "concept_hubs",
        "concept_hub_bridges",
        "concept_hub_nodes",
        "concept_hub_domain_dict",
        "largo_plazo",
        "corto_plazo",
    ]

    for tabla in tablas:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            reporte["filas_por_tabla"][tabla] = cur.fetchone()[0]
        except sqlite3.OperationalError as e:
            reporte["filas_por_tabla"][tabla] = f"Error / No existe: {e}"

    # 1. Bridges huérfanos (hub_id no existe en concept_hubs)
    try:
        cur.execute("""
            SELECT b.hub_id, b.bridge_text
            FROM concept_hub_bridges b
            LEFT JOIN concept_hubs h ON h.hub_id = b.hub_id
            WHERE h.hub_id IS NULL
        """)
        reporte["bridges_huerfanos"] = [{"hub_id": r[0], "bridge_text": r[1]} for r in cur.fetchall()]
    except Exception as e:
        reporte["bridges_huerfanos"] = str(e)

    # 2. Nodos relacionados huérfanos (hub_id no existe en concept_hubs)
    try:
        cur.execute("""
            SELECT n.hub_id, n.node_concepto, n.role
            FROM concept_hub_nodes n
            LEFT JOIN concept_hubs h ON h.hub_id = n.hub_id
            WHERE h.hub_id IS NULL
        """)
        reporte["nodos_relacionados_huerfanos"] = [{"hub_id": r[0], "node_concepto": r[1], "role": r[2]} for r in cur.fetchall()]
    except Exception as e:
        reporte["nodos_relacionados_huerfanos"] = str(e)

    # 3. Canonical nodes inexistentes en largo_plazo y corto_plazo
    try:
        cur.execute("""
            SELECT h.hub_id, h.canonical_node
            FROM concept_hubs h
            WHERE h.canonical_node NOT IN (SELECT concepto FROM largo_plazo)
              AND h.canonical_node NOT IN (SELECT concepto FROM corto_plazo)
        """)
        reporte["canonical_nodes_inexistentes"] = [{"hub_id": r[0], "canonical_node": r[1]} for r in cur.fetchall()]
    except Exception as e:
        reporte["canonical_nodes_inexistentes"] = str(e)

    # 4. node_concepto inexistentes en largo_plazo y corto_plazo
    try:
        cur.execute("""
            SELECT n.hub_id, n.node_concepto, n.role
            FROM concept_hub_nodes n
            WHERE n.node_concepto NOT IN (SELECT concepto FROM largo_plazo)
              AND n.node_concepto NOT IN (SELECT concepto FROM corto_plazo)
        """)
        reporte["node_conceptos_inexistentes"] = [{"hub_id": r[0], "node_concepto": r[1], "role": r[2]} for r in cur.fetchall()]
    except Exception as e:
        reporte["node_conceptos_inexistentes"] = str(e)

    # 5. Bridges repetidos por hub o globales
    try:
        cur.execute("""
            SELECT hub_id, bridge_text, COUNT(*) as cnt
            FROM concept_hub_bridges
            GROUP BY hub_id, LOWER(TRIM(bridge_text))
            HAVING cnt > 1
        """)
        reporte["bridges_repetidos"] = [{"hub_id": r[0], "bridge_text": r[1], "count": r[2]} for r in cur.fetchall()]
    except Exception as e:
        reporte["bridges_repetidos"] = str(e)

    # 6. Inspección de cada hub: conteo de bridges y ángulos
    # Chequear si existe la columna angle en concept_hub_bridges
    cur.execute("PRAGMA table_info(concept_hub_bridges)")
    cols_bridge = [c[1] for c in cur.fetchall()]
    tiene_col_angle = "angle" in cols_bridge

    try:
        cur.execute("SELECT hub_id, canonical_node, description FROM concept_hubs")
        hubs = cur.fetchall()
        for hub_id, canonical, desc in hubs:
            if tiene_col_angle:
                cur.execute("SELECT bridge_text, angle, weight FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,))
                bridges_rows = cur.fetchall()
                bridges = [{"text": r[0], "angle": r[1], "weight": r[2]} for r in bridges_rows]
                angulos = {r[1] for r in bridges_rows if r[1]}
            else:
                cur.execute("SELECT bridge_text, weight FROM concept_hub_bridges WHERE hub_id = ?", (hub_id,))
                bridges_rows = cur.fetchall()
                bridges = [{"text": r[0], "angle": None, "weight": r[1]} for r in bridges_rows]
                angulos = set()

            cur.execute("SELECT node_concepto, role FROM concept_hub_nodes WHERE hub_id = ?", (hub_id,))
            nodos_rel = [{"concepto": r[0], "role": r[1]} for r in cur.fetchall()]

            hub_info = {
                "hub_id": hub_id,
                "canonical_node": canonical,
                "description": desc,
                "total_bridges": len(bridges),
                "angulos_distintos": list(angulos),
                "total_nodos_relacionados": len(nodos_rel),
            }
            reporte["detalle_hubs"].append(hub_info)

            if len(bridges) < 5:
                reporte["hubs_con_menos_de_5_bridges"].append({"hub_id": hub_id, "count": len(bridges)})
            
            angulos_esperados = {"sinonimo", "problema", "solucion", "situacion", "ingenuo"}
            if not angulos_esperados.issubset(angulos):
                reporte["hubs_sin_5_angulos"].append({
                    "hub_id": hub_id,
                    "angulos_presentes": list(angulos),
                    "faltantes": list(angulos_esperados - angulos)
                })
    except Exception as e:
        reporte["error_inspeccion_hubs"] = str(e)

    conn.close()
    return reporte

if __name__ == "__main__":
    db_target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BIORAG_PATH", "MemoryBioRAG_Data/memory_biorag.db")
    resultado = auditar_base_datos(db_target)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    
    os.makedirs("docs", exist_ok=True)
    with open("docs/auditoria_concept_hub_inicial.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print("\n[OK] Reporte guardado en docs/auditoria_concept_hub_inicial.json")
