#!/usr/bin/env python3
"""
Phase 2D: Herramienta de marcado de utilidad de búsquedas.

Muestra las últimas búsquedas registradas en log_busquedas y permite
marcarlas como útiles (1) o inútiles (0) para alimentar tests de regresión.

Uso:
    python3 scripts/marcar_resultado.py          # Muestra últimas 20 búsquedas
    python3 scripts/marcar_resultado.py --limit 50  # Muestra últimas 50
    python3 scripts/marcar_resultado.py --stats   # Muestra estadísticas agregadas
"""
import sys
import os
import sqlite3
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.environ.get("BIORAG_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "MemoryBioRAG_Data", "memory_biorag.db"
))


def mostrar_busquedas(conn, limit=20):
    """Muestra las últimas búsquedas con su estado de utilidad."""
    cur = conn.execute(
        "SELECT id, query, resultados_count, top_score, creado_en, util "
        "FROM log_busquedas ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = cur.fetchall()
    if not rows:
        print("No hay búsquedas registradas en log_busquedas.")
        return []

    print(f"\n{'ID':>5}  {'Util':>5}  {'Res':>4}  {'Score':>6}  {'Fecha':>19}  Query")
    print("-" * 80)
    for row in rows:
        id_, query, count, score, ts, util = row
        fecha = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "?"
        score_str = f"{score:.2f}" if score is not None else "  -  "
        util_str = {1: "  Y", 0: "  N", None: "  ?"}.get(util, "  ?")
        query_trunc = (query[:45] + "...") if len(query) > 48 else query
        print(f"{id_:>5}  {util_str:>5}  {count:>4}  {score_str:>6}  {fecha:>19}  {query_trunc}")

    return rows


def marcar(conn, id_, valor):
    """Marca una búsqueda como útil (1) o inútil (0)."""
    conn.execute("UPDATE log_busquedas SET util = ? WHERE id = ?", (valor, id_))
    conn.commit()
    print(f"  Búsqueda #{id_} marcada como {'útil' if valor else 'inútil'}.")


def mostrar_stats(conn):
    """Muestra estadísticas agregadas del log."""
    cur = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN util = 1 THEN 1 ELSE 0 END) as utiles,
            SUM(CASE WHEN util = 0 THEN 1 ELSE 0 END) as inutiles,
            SUM(CASE WHEN util IS NULL THEN 1 ELSE 0 END) as sin_marcar,
            AVG(resultados_count) as avg_resultados,
            AVG(CASE WHEN top_score IS NOT NULL THEN top_score END) as avg_score,
            AVG(CASE WHEN util = 1 AND top_score IS NOT NULL THEN top_score END) as avg_score_util,
            AVG(CASE WHEN util = 0 AND top_score IS NOT NULL THEN top_score END) as avg_score_inutil
        FROM log_busquedas
    """)
    row = cur.fetchone()
    total, utiles, inutiles, sin_marcar, avg_res, avg_score, avg_u, avg_i = row

    print(f"\n--- Estadísticas de log_busquedas ---")
    print(f"  Total búsquedas:     {total}")
    print(f"  Útiles:              {utiles}")
    print(f"  Inútiles:            {inutiles}")
    print(f"  Sin marcar:          {sin_marcar}")
    print(f"  Promedio resultados: {avg_res:.1f}" if avg_res else "  Promedio resultados: -")
    print(f"  Score promedio:      {avg_score:.3f}" if avg_score else "  Score promedio:      -")
    if avg_u is not None:
        print(f"  Score prom. útiles:  {avg_u:.3f}")
    if avg_i is not None:
        print(f"  Score prom. inútiles:{avg_i:.3f}")
    print()


def modo_interactivo(conn):
    """Bucle interactivo para marcar búsquedas."""
    rows = mostrar_busquedas(conn)
    if not rows:
        return

    print("\nComandos: <id> y (útil) | <id> n (inútil) | q (salir) | r (refrescar)")
    while True:
        try:
            entrada = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if entrada in ("q", "quit", "exit"):
            break
        if entrada in ("r", "refresh"):
            mostrar_busquedas(conn)
            continue

        parts = entrada.split()
        if len(parts) != 2:
            print("  Formato: <id> y | <id> n")
            continue

        try:
            id_ = int(parts[0])
        except ValueError:
            print("  ID debe ser numérico.")
            continue

        if parts[1] in ("y", "Y", "1", "si", "yes"):
            marcar(conn, id_, 1)
        elif parts[1] in ("n", "N", "0", "no"):
            marcar(conn, id_, 0)
        else:
            print("  Usar 'y' (útil) o 'n' (inútil).")


def main():
    parser = argparse.ArgumentParser(description="Marcador de utilidad de búsquedas BioRAG")
    parser.add_argument("--limit", type=int, default=20, help="Cantidad de búsquedas a mostrar")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas agregadas")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Ruta a la base de datos")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Base de datos no encontrada: {args.db}")
        sys.exit(1)

    conn = sqlite3.connect(args.db)

    # Verificar que la tabla existe
    cur = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='log_busquedas'")
    if cur.fetchone()[0] == 0:
        print("La tabla log_busquedas no existe. Ejecuta una búsqueda primero para crearla.")
        conn.close()
        sys.exit(1)

    if args.stats:
        mostrar_stats(conn)
    else:
        modo_interactivo(conn)

    conn.close()


if __name__ == "__main__":
    main()
