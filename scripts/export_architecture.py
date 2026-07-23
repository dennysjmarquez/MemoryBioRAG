#!/usr/bin/env python3
"""Exporta la arquitectura completa de la DB BioRAG a un archivo de texto plano.

Genera un blueprint autodescriptivo que cualquier IA puede leer para entender
la estructura, estado actual y filosofía del sistema BioRAG.

TODO es dinámico: lee esquema, datos, stats directo de la DB.
Sin strings hardcodeados que queden obsoletos.
Si se agrega una tabla o columna nueva, se incluye automáticamente.

Uso:
    python3 scripts/export_architecture.py [ruta_db]
"""

import sqlite3
import os
import sys
from datetime import datetime

# ── Rutas ───────────────────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

DB_PATH = os.environ.get("BIORAG_PATH") or os.path.join(
    _PROJECT_ROOT, "MemoryBioRAG_Data", "memory_biorag.db"
)

OUTPUT_PATH = os.path.join(_PROJECT_ROOT, "db_architecture_export.txt")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _section(title: str) -> str:
    return f"\n{'=' * 70}\n  {title}\n{'=' * 70}\n"


def _subsection(title: str) -> str:
    return f"\n--- {title} ---\n"


def _truncate(text, max_chars: int = 200) -> str:
    if not text:
        return ""
    text = str(text)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _table_exists(c: sqlite3.Cursor, table_name: str) -> bool:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return c.fetchone() is not None


def _get_columns(c: sqlite3.Cursor, table_name: str) -> list[str]:
    """Retorna los nombres de las columnas reales de una tabla."""
    c.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in c.fetchall()]


def _column_exists(c: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Verifica si una columna existe en una tabla."""
    return column_name in _get_columns(c, table_name)


def _get_tables(c: sqlite3.Cursor) -> list[str]:
    """Retorna todas las tablas (excluyendo tablas internas de SQLite y FTS)."""
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts_%' "
        "AND name NOT LIKE 'largo_plazo_fts' ORDER BY name"
    )
    return [row[0] for row in c.fetchall()]


def _safe_count(c: sqlite3.Cursor, table: str, where: str = "") -> int:
    try:
        sql = f"SELECT COUNT(*) FROM \"{table}\""
        if where:
            sql += f" WHERE {where}"
        c.execute(sql)
        return c.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _safe_query(c: sqlite3.Cursor, sql: str) -> list[tuple]:
    """Ejecuta un query y retorna filas, o lista vacía si falla."""
    try:
        c.execute(sql)
        return c.fetchall()
    except sqlite3.OperationalError:
        return []


def _format_value(val, col_name: str = "") -> str:
    """Formatea un valor para display, manejando NULLs y tipos."""
    if val is None:
        return "-"
    if isinstance(val, float):
        return f"{val:.3f}"
    if isinstance(val, int) and "timestamp" in col_name.lower():
        try:
            return datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            return str(val)
    s = str(val)
    return _truncate(s, 150) if len(s) > 150 else s


# ── Exportadores dinámicos ──────────────────────────────────────────────────

def _export_header(db_path: str) -> list[str]:
    out = []
    out.append("=" * 70)
    out.append("  BioRAG — Database Architecture Export (Blueprint Dinámico)")
    out.append("=" * 70)
    out.append(f"  Archivo DB:    {os.path.basename(db_path)}")
    out.append(f"  Ruta (relativa): {os.path.relpath(db_path, _PROJECT_ROOT)}")
    out.append(f"  Generado:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        size = os.path.getsize(db_path)
        out.append(f"  Tamaño DB:     {size:,} bytes ({size / 1024:.1f} KB)")
    except OSError:
        pass
    out.append("=" * 70)
    out.append("")
    out.append("Este blueprint se genera dinámicamente desde la DB.")
    out.append("Refleja el estado REAL del sistema en el momento de la exportación.")
    out.append("Si se agrega una tabla o columna, se incluye automáticamente.")
    out.append("")
    return out


def _export_db_info(c: sqlite3.Cursor) -> list[str]:
    out = [_section("INFORMACIÓN DE LA BASE DE DATOS")]
    try:
        c.execute("PRAGMA journal_mode")
        out.append(f"  Journal mode:    {c.fetchone()[0]}")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("PRAGMA page_count")
        pages = c.fetchone()[0]
        c.execute("PRAGMA page_size")
        page_size = c.fetchone()[0]
        out.append(f"  Tamaño total:    {pages * page_size:,} bytes ({pages * page_size / 1024:.1f} KB)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("PRAGMA freelist_count")
        out.append(f"  Páginas libres:  {c.fetchone()[0]}")
    except sqlite3.OperationalError:
        pass
    out.append("")
    return out


def _export_schema(c: sqlite3.Cursor) -> list[str]:
    out = [_section("ESQUEMA DE LA BASE DE DATOS")]

    out.append(_subsection("TABLAS"))
    c.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND sql IS NOT NULL ORDER BY name"
    )
    for name, sql in c.fetchall():
        count = _safe_count(c, name)
        out.append(f"-- {name} ({count} filas)")
        out.append(sql + ";")
        out.append("")

    out.append(_subsection("ÍNDICES"))
    c.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND sql IS NOT NULL ORDER BY name"
    )
    for name, sql in c.fetchall():
        out.append(sql + ";")
    out.append("")

    out.append(_subsection("TRIGGERS"))
    c.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='trigger' ORDER BY name"
    )
    for name, sql in c.fetchall():
        out.append(f"-- {name}")
        out.append(sql + ";")
        out.append("")

    out.append(_subsection("VISTAS"))
    c.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='view' AND sql IS NOT NULL ORDER BY name"
    )
    rows = c.fetchall()
    if rows:
        for name, sql in rows:
            out.append(f"-- {name}")
            out.append(sql + ";")
            out.append("")
    else:
        out.append("(ninguna)")

    return out


def _export_categories(c: sqlite3.Cursor) -> list[str]:
    """Exporta categorías de forma dinámica — lee columnas reales."""
    out = [_section("CATEGORÍAS")]

    if not _table_exists(c, "categories"):
        out.append("(tabla categories no existe)")
        return out

    cols = _get_columns(c, "categories")
    out.append(f"  Columnas: {', '.join(cols)}")
    out.append("")

    # Buscar columnas conocidas de forma dinámica
    id_col = "id" if "id" in cols else cols[0] if cols else None
    name_col = "name" if "name" in cols else None
    desc_col = "description" if "description" in cols else None
    decay_col = "decay_rate" if "decay_rate" in cols else None

    if not id_col or not name_col:
        out.append("  (columnas insuficientes para mostrar detalle)")
        return out

    select_cols = [id_col, name_col]
    if desc_col:
        select_cols.append(desc_col)
    if decay_col:
        select_cols.append(decay_col)

    c.execute(f"SELECT {', '.join(select_cols)} FROM categories ORDER BY {id_col}")
    rows = c.fetchall()

    # Header dinámico
    header = f"  {id_col:<6} {name_col:<20}"
    widths = [6, 20]
    if desc_col:
        header += f" {desc_col:<30}"
        widths.append(30)
    if decay_col:
        header += f" {decay_col:<10}"
        widths.append(10)
    out.append(header)
    out.append("-" * sum(w + 2 for w in widths))

    for row in rows:
        line = f"  {str(row[0]):<6} {str(row[1]):<20}"
        if desc_col and len(row) > 2:
            line += f" {str(row[2]):<30}"
        if decay_col and len(row) > 3:
            line += f" {str(row[3]):<10}"
        out.append(line)
    out.append("")
    return out


def _export_stats(c: sqlite3.Cursor) -> list[str]:
    out = [_section("ESTADÍSTICAS ACTUALES")]

    # Conteos dinámicos de todas las tablas
    out.append(_subsection("CONTEOS POR TABLA"))
    tables = _get_tables(c)
    for table in tables:
        count = _safe_count(c, table)
        out.append(f"  {table:<40} {count:>8} filas")
    out.append("")

    # Detalle de largo_plazo si existe
    if _table_exists(c, "largo_plazo"):
        out.append(_subsection("LARGO PLAZO"))
        activos = _safe_count(c, "largo_plazo", "estado = 'activo'")
        dormidos = _safe_count(c, "largo_plazo", "estado = 'dormido'")
        total = _safe_count(c, "largo_plazo")

        energia = 0
        if _column_exists(c, "largo_plazo", "peso_sinaptico"):
            try:
                c.execute("SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado='activo'")
                energia = c.fetchone()[0] or 0
            except sqlite3.OperationalError:
                pass

        out.append(f"  Total:           {total}")
        out.append(f"  Activos:         {activos}")
        out.append(f"  Dormidos:        {dormidos}")
        out.append(f"  Energía total:   {energia}")
        out.append("")

        # Distribución por categoría (dinámico)
        if _column_exists(c, "largo_plazo", "categoria") and _table_exists(c, "categories"):
            out.append(_subsection("DISTRIBUCIÓN POR CATEGORÍA"))
            c.execute("""
                SELECT c.name, COUNT(lp.concepto),
                       SUM(CASE WHEN lp.estado = 'activo' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN lp.estado = 'dormido' THEN 1 ELSE 0 END),
                       ROUND(AVG(lp.peso_sinaptico), 2)
                FROM largo_plazo lp JOIN categories c ON lp.categoria = c.id
                GROUP BY c.name ORDER BY COUNT(lp.concepto) DESC
            """)
            out.append(
                f"{'Categoría':<15} {'Total':<8} {'Activos':<8} {'Dormidos':<8} {'Peso Prom.':<10}"
            )
            out.append("-" * 55)
            for name, total, act, dorm, peso in c.fetchall():
                out.append(f"{name:<15} {total:<8} {act:<8} {dorm:<8} {peso:<10}")
            out.append("")

    return out


def _export_fts_config(c: sqlite3.Cursor) -> list[str]:
    out = [_section("CONFIGURACIÓN FTS5")]

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fts%'")
    fts_tables = [row[0] for row in c.fetchall()]

    if not fts_tables:
        out.append("(sin tablas FTS5)")
        return out

    out.append(f"  Tablas FTS5: {', '.join(fts_tables)}")
    out.append("")

    for fts_table in fts_tables:
        out.append(_subsection(f"FTS: {fts_table}"))
        try:
            c.execute(f"SELECT COUNT(*) FROM \"{fts_table}\"")
            count = c.fetchone()[0]
            out.append(f"  Documentos indexados: {count}")
        except sqlite3.OperationalError:
            out.append("  (no se pudo leer)")
        out.append("")

    return out


def _export_indexes(c: sqlite3.Cursor) -> list[str]:
    out = [_section("ÍNDICES PERSONALIZADOS")]
    c.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY name
    """)
    rows = c.fetchall()
    if rows:
        for name, sql in rows:
            out.append(f"  {name}")
            out.append(f"    {sql}")
    else:
        out.append("  (sin índices personalizados)")
    out.append("")
    return out


def _export_topology(c: sqlite3.Cursor) -> list[str]:
    """Topología del grafo sináptico — dinámico."""
    out = [_section("TOPOLOGÍA DEL GRAFO SINÁPTICO")]

    if not _table_exists(c, "sinapsis"):
        out.append("(tabla sinapsis no existe)")
        return out

    cols = _get_columns(c, "sinapsis")
    out.append(f"  Columnas: {', '.join(cols)}")
    out.append("")

    # Distribución de tipos de arista (si existe columna 'tipo')
    if "tipo" in cols and "peso" in cols:
        out.append(_subsection("DISTRIBUCIÓN POR TIPO DE ARISTA"))
        c.execute("""
            SELECT tipo, COUNT(*), ROUND(AVG(peso), 3), ROUND(MIN(peso), 3), ROUND(MAX(peso), 3)
            FROM sinapsis GROUP BY tipo ORDER BY COUNT(*) DESC
        """)
        rows = c.fetchall()
        if rows:
            out.append(f"{'Tipo':<22} {'Cantidad':<10} {'Peso Prom.':<12} {'Mín':<8} {'Máx':<8}")
            out.append("-" * 60)
            for tipo, cnt, avg_p, min_p, max_p in rows:
                out.append(f"{tipo:<22} {cnt:<10} {avg_p:<12} {min_p:<8} {max_p:<8}")
        else:
            out.append("  (sin aristas)")
        out.append("")

    # Orígenes y destinos únicos (si existen columnas 'origen', 'destino')
    if "origen" in cols and "destino" in cols:
        try:
            origenes = c.execute("SELECT COUNT(DISTINCT origen) FROM sinapsis").fetchone()[0]
            destinos = c.execute("SELECT COUNT(DISTINCT destino) FROM sinapsis").fetchone()[0]
            out.append(f"  Nodos origen únicos:  {origenes}")
            out.append(f"  Nodos destino únicos: {destinos}")
        except sqlite3.OperationalError:
            pass
        out.append("")

    return out


def _export_metrics(c: sqlite3.Cursor) -> list[str]:
    """Métricas cognitivas y de rendimiento — 100% dinámico."""
    out = [_section("MÉTRICAS COGNITIVAS")]

    # ── Ciclos de sueño ─────────────────────────────────────────────────
    if _table_exists(c, "metricas_cognitivas"):
        out.append(_subsection("ÚLTIMOS CICLOS DE SUEÑO"))
        cols = _get_columns(c, "metricas_cognitivas")
        out.append(f"  Columnas: {', '.join(cols)}")
        out.append("")

        # Construir SELECT dinámico con las columnas que existen
        known_cols = {
            "timestamp": "timestamp",
            "nodos_consolidados": "consolidados",
            "nodos_dormidos_ciclo": "dormidos",
            "sinapsis_creadas": "sin.creadas",
            "sinapsis_podadas": "sin.podadas",
            "ratio_consolidacion": "ratio",
        }

        select_parts = []
        col_aliases = []
        for real_col, alias in known_cols.items():
            if real_col in cols:
                select_parts.append(real_col)
                if real_col != "timestamp":  # Ya se muestra como "Fecha"
                    col_aliases.append(alias)

        # Buscar columna de categoría dominante (puede llamarse distinto)
        cat_col = None
        for candidate in ["categoria_dominante_id", "categoria_dominante", "cat_dominante"]:
            if candidate in cols:
                cat_col = candidate
                break

        ts_col = "timestamp" if "timestamp" in cols else None

        if select_parts and ts_col:
            # Agregar JOIN con categories si hay columna de categoría FK
            from_clause = "metricas_cognitivas"
            cat_join_alias = None
            if cat_col and _table_exists(c, "categories") and _column_exists(c, "categories", "name"):
                from_clause = "metricas_cognitivas mc LEFT JOIN categories cat ON mc.{cat_col} = cat.id".format(cat_col=cat_col)
                cat_join_alias = "cat.name"
                select_parts_full = []
                for p in select_parts:
                    select_parts_full.append(f"mc.{p}")
                select_str = ", ".join(select_parts_full)
                select_str += f", {cat_join_alias} as cat_name"
            else:
                select_str = ", ".join(select_parts)
                if cat_col:
                    select_str += f", {cat_col}"

            order_col = f"mc.{ts_col}" if cat_join_alias else ts_col
            c.execute(f"SELECT {select_str} FROM {from_clause} ORDER BY {order_col} DESC LIMIT 5")
            rows = c.fetchall()

            if rows:
                # Header
                header = f"  {'Fecha':<22}"
                for alias in col_aliases:
                    header += f" {alias:<14}"
                if cat_col:
                    header += f" {'Cat.Dom.':<15}"
                out.append(header)
                out.append("-" * (22 + 14 * len(col_aliases) + 15))

                for row in rows:
                    ts_val = row[0]
                    try:
                        fecha = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M")
                    except (ValueError, OSError):
                        fecha = str(ts_val)
                    line = f"  {fecha:<22}"
                    # select_parts incluye timestamp en el conteo, pero ya lo formateamos
                    # como fecha. Iteramos desde 1 (skip timestamp) hasta len-1 para no
                    # incluir cat_name que puede estar al final.
                    data_end = len(row) - 1 if cat_col else len(row)
                    for i in range(1, data_end):
                        val = row[i]
                        line += f" {_format_value(val):<14}"
                    if cat_col:
                        cat_val = row[-1]
                        cat_str = str(cat_val) if cat_val else "-"
                        line += f" {cat_str:<15}"
                    out.append(line)
            else:
                out.append("  (sin ciclos de sueño registrados)")
            out.append("")

    # ── Métricas de rendimiento ─────────────────────────────────────────
    if _table_exists(c, "metricas_rendimiento"):
        out.append(_subsection("MÉTRICAS DE RENDIMIENTO"))
        cols = _get_columns(c, "metricas_rendimiento")
        out.append(f"  Columnas: {', '.join(cols)}")
        out.append("")

        ts_col = "timestamp" if "timestamp" in cols else None
        if ts_col:
            # Seleccionar todas las columnas excepto id y timestamp para display
            display_cols = [col for col in cols if col not in ("id",)]
            c.execute(f"SELECT {', '.join(display_cols)} FROM metricas_rendimiento ORDER BY {ts_col} DESC LIMIT 3")
            rows = c.fetchall()

            if rows:
                header = "  " + " ".join(f"{col:<18}" for col in display_cols)
                out.append(header)
                out.append("-" * (18 * len(display_cols) + 2))
                for row in rows:
                    line = "  "
                    for i, col in enumerate(display_cols):
                        val = row[i]
                        if "timestamp" in col.lower() and isinstance(val, (int, float)):
                            try:
                                val = datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M")
                            except (ValueError, OSError):
                                pass
                        elif "tamano_db" in col.lower() and isinstance(val, (int, float)):
                            val = f"{val / 1024:.0f} KB"
                        elif isinstance(val, float):
                            val = f"{val:.2f}"
                        line += f"{str(val):<18}"
                    out.append(line)
            else:
                out.append("  (sin mediciones de rendimiento)")
            out.append("")

    return out


def _export_memory_snapshot(c: sqlite3.Cursor) -> list[str]:
    """Snapshot de memorias — dinámico."""
    out = [_section("SNAPSHOT DE MEMORIAS")]

    if not _table_exists(c, "largo_plazo"):
        out.append("(tabla largo_plazo no existe)")
        return out

    cols = _get_columns(c, "largo_plazo")
    has_concepto = "concepto" in cols
    has_peso = "peso_sinaptico" in cols
    has_estado = "estado" in cols
    has_syn = "sinonimos" in cols
    has_contenido = "contenido" in cols
    has_categoria = "categoria" in cols and _table_exists(c, "categories")

    # Nodos activos
    out.append(_subsection("NODOS ACTIVOS"))
    try:
        if has_concepto and has_peso:
            select = ["lp.concepto", "lp.peso_sinaptico"]
            if has_syn:
                select.append("lp.sinonimos")
            if has_contenido:
                select.append("lp.contenido")
            if has_categoria:
                select.insert(1, "c.name as cat_name")
                from_clause = "largo_plazo lp JOIN categories c ON lp.categoria = c.id"
            else:
                from_clause = "largo_plazo lp"

            where = "WHERE lp.estado = 'activo'" if has_estado else ""
            order = "ORDER BY lp.peso_sinaptico DESC" if has_peso else ""

            c.execute(f"SELECT {', '.join(select)} FROM {from_clause} {where} {order}")
            rows = c.fetchall()

            if rows:
                for row in rows:
                    concepto = row[0]
                    peso = row[1] if has_peso else "?"
                    idx = 2
                    cat_name = None
                    if has_categoria:
                        cat_name = row[idx]
                        idx += 1
                    syn = row[idx] if has_syn else None
                    if has_syn:
                        idx += 1
                    contenido = row[idx] if has_contenido else None

                    prefix = f"  [{cat_name}] " if cat_name else "  "
                    out.append(f"{prefix}{concepto} (peso: {peso})")
                    if syn:
                        out.append(f"    Sinónimos: {syn}")
                    if contenido:
                        out.append(f"    {_truncate(contenido)}")
                    out.append("")
            else:
                out.append("  (sin nodos activos)")
    except sqlite3.OperationalError as e:
        out.append(f"  (error leyendo nodos: {e})")

    # Nodos dormidos
    out.append(_subsection("NODOS DORMIDOS"))
    try:
        if has_concepto and has_peso and has_estado:
            c.execute("""
                SELECT concepto, peso_sinaptico
                FROM largo_plazo WHERE estado = 'dormido'
                ORDER BY peso_sinaptico DESC
            """)
            dormidos = c.fetchall()
            if dormidos:
                out.append(f"  {'Concepto':<55} {'Peso':<8}")
                out.append("  " + "-" * 63)
                for concepto, peso in dormidos:
                    out.append(f"  {concepto:<55} {peso:<8}")
            else:
                out.append("  (ninguno)")
        else:
            out.append("  (columnas insuficientes)")
    except sqlite3.OperationalError as e:
        out.append(f"  (error: {e})")
    out.append("")

    # Corto plazo pendiente
    if _table_exists(c, "corto_plazo"):
        out.append(_subsection("CORTO PLAZO (pendiente de consolidación)"))
        count = _safe_count(c, "corto_plazo")
        if count > 0:
            out.append(f"  ({count} recuerdos pendientes)")
        else:
            out.append("  (vacío — todo consolidado)")
        out.append("")

    return out


def _export_synapses(c: sqlite3.Cursor) -> list[str]:
    """Aristas sinápticas — dinámico."""
    out = [_section("GRAFO SINÁPTICO (aristas)")]

    if not _table_exists(c, "sinapsis"):
        out.append("(tabla sinapsis no existe)")
        return out

    cols = _get_columns(c, "sinapsis")
    out.append(f"  Columnas: {', '.join(cols)}")
    out.append("")

    # Seleccionar columnas conocidas que existan
    known = ["origen", "destino", "peso", "tipo"]
    select = [col for col in known if col in cols]
    if not select:
        select = cols[:4]  # fallback: primeras 4 columnas

    order = "peso" if "peso" in cols else cols[0]
    c.execute(f"SELECT {', '.join(select)} FROM sinapsis ORDER BY {order} DESC")
    rows = c.fetchall()

    out.append(f"Total aristas: {len(rows)}")
    out.append("")
    if rows:
        # Header dinámico
        header = "  " + " ".join(f"{col:<22}" for col in select)
        out.append(header)
        out.append("  " + "-" * (22 * len(select)))
        for row in rows:
            line = "  "
            for i, col in enumerate(select):
                val = row[i]
                if isinstance(val, float):
                    line += f"{val:<22.3f}"
                else:
                    line += f"{str(val):<22}"
            out.append(line)
    else:
        out.append("  (sin aristas)")
    out.append("")
    return out


def _export_semantic_groups(c: sqlite3.Cursor) -> list[str]:
    """Grupos semánticos WordNet — dinámico."""
    out = [_section("GRUPOS SEMÁNTICOS (WordNet)")]

    if not _table_exists(c, "grupos_semanticos"):
        out.append("(tabla grupos_semanticos no existe — WordNet no configurado)")
        return out

    cols = _get_columns(c, "grupos_semanticos")
    out.append(f"  Columnas: {', '.join(cols)}")
    out.append("")

    c.execute("SELECT COUNT(*) FROM grupos_semanticos")
    total_grupos = c.fetchone()[0]

    if _table_exists(c, "nodo_grupos_semanticos"):
        c.execute("SELECT COUNT(*) FROM nodo_grupos_semanticos")
        total_rel = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT concepto) FROM nodo_grupos_semanticos")
        nodos_clasificados = c.fetchone()[0]
    else:
        total_rel = 0
        nodos_clasificados = 0

    out.append(f"  Grupos:            {total_grupos}")
    out.append(f"  Relaciones:        {total_rel}")
    out.append(f"  Nodos clasificados: {nodos_clasificados}")
    out.append("")

    # Top 10 grupos por uso
    if _table_exists(c, "nodo_grupos_semanticos"):
        out.append(_subsection("TOP 10 GRUPOS POR USO"))
        ngs_cols = _get_columns(c, "nodo_grupos_semanticos")
        if "concepto" in ngs_cols and "grupo_id" in ngs_cols and "nombre" in cols:
            c.execute("""
                SELECT gs.nombre, COUNT(ngs.concepto) as uso
                FROM grupos_semanticos gs
                JOIN nodo_grupos_semanticos ngs ON gs.id = ngs.grupo_id
                GROUP BY gs.nombre
                ORDER BY uso DESC
                LIMIT 10
            """)
            rows = c.fetchall()
            if rows:
                out.append(f"  {'Grupo':<30} {'Nodos':<8}")
                out.append("  " + "-" * 38)
                for nombre, uso in rows:
                    out.append(f"  {nombre:<30} {uso:<8}")
        out.append("")

    return out


def _export_communications(c: sqlite3.Cursor) -> list[str]:
    """Comunicaciones entre agentes — dinámico."""
    out = [_section("COMUNICACIONES ENTRE AGENTES (últimos 10)")]

    if not _table_exists(c, "comunicaciones"):
        out.append("(tabla comunicaciones no existe)")
        return out

    cols = _get_columns(c, "comunicaciones")
    out.append(f"  Columnas: {', '.join(cols)}")
    out.append("")

    # Seleccionar columnas conocidas que existan
    known = ["origen", "destino", "contenido", "timestamp", "leido"]
    select = [col for col in known if col in cols]
    if not select:
        select = cols

    order = "timestamp" if "timestamp" in cols else cols[0]
    c.execute(f"SELECT {', '.join(select)} FROM comunicaciones ORDER BY {order} DESC LIMIT 10")
    rows = c.fetchall()

    if rows:
        for row in rows:
            # Buscar valores por nombre de columna
            vals = {col: row[i] for i, col in enumerate(select)}

            ts = vals.get("timestamp")
            if ts and isinstance(ts, (int, float)):
                try:
                    fecha = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                except (ValueError, OSError):
                    fecha = str(ts)
            else:
                fecha = str(ts) if ts else "?"

            origen = vals.get("origen", "?")
            destino = vals.get("destino", "?")
            leido = vals.get("leido")
            contenido = vals.get("contenido", "")

            estado = "leído" if leido else "NO LEÍDO" if leido is not None else ""
            estado_str = f" ({estado})" if estado else ""

            out.append(f"  [{fecha}] {origen} -> {destino}{estado_str}")
            if contenido:
                out.append(f"    {_truncate(contenido, 300)}")
            out.append("")
    else:
        out.append("  (sin mensajes)")
    out.append("")
    return out


def _export_generic_tables(c: sqlite3.Cursor, tables: list[str]) -> list[str]:
    """Exporta tablas que no tienen exportador especializado — genérico y dinámico."""
    # Tablas que ya se exportan con exportadores especializados
    skip = {
        "categories", "largo_plazo", "sinapsis", "metricas_cognitivas",
        "metricas_rendimiento", "grupos_semanticos", "nodo_grupos_semanticos",
        "comunicaciones", "largo_plazo_backup",
    }
    # Tablas internas de FTS y SQLite
    skip.update(t for t in tables if "fts" in t.lower() or t.startswith("sqlite_"))

    out = [_section("DATOS DE TABLAS COMPLEMENTARIAS")]

    exported_any = False
    for table in tables:
        if table in skip:
            continue

        cols = _get_columns(c, table)
        if not cols:
            continue

        count = _safe_count(c, table)
        out.append(_subsection(f"{table} ({count} filas)"))
        out.append(f"  Columnas: {', '.join(cols)}")

        if count == 0:
            out.append("  (vacía)")
            out.append("")
            continue

        # Exportar hasta 10 filas como preview
        limit = 10
        c.execute(f"SELECT * FROM \"{table}\" ORDER BY ROWID DESC LIMIT {limit}")
        rows = c.fetchall()

        if rows:
            # Header
            header = "  " + " ".join(f"{col[:18]:<20}" for col in cols)
            out.append(header)
            out.append("  " + "-" * (20 * len(cols)))

            for row in rows:
                line = "  "
                for i, val in enumerate(row):
                    formatted = _format_value(val, cols[i] if i < len(cols) else "")
                    line += f"{formatted[:18]:<20} "
                out.append(line)

            if count > limit:
                out.append(f"  ... ({count - limit} filas más)")
        else:
            out.append("  (sin datos)")

        out.append("")
        exported_any = True

    if not exported_any:
        out.append("  (todas las tablas ya tienen exportador especializado)")

    return out


def _export_foreign_keys(c: sqlite3.Cursor) -> list[str]:
    """Extrae todas las relaciones FK de la DB y las presenta de forma legible."""
    out = [_section("RELACIONES DE REFERENCIA (Foreign Keys)")]

    c.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='table' AND sql IS NOT NULL AND sql LIKE '%FOREIGN%'
        ORDER BY name
    """)
    tables = c.fetchall()

    if not tables:
        out.append("(sin foreign keys definidas)")
        out.append("")
        return out

    for table_name, sql in tables:
        out.append(_subsection(table_name))
        # Extraer líneas de FOREIGN KEY del SQL
        for line in sql.split('\n'):
            stripped = line.strip().upper()
            if stripped.startswith('FOREIGN KEY'):
                out.append(f"  {line.strip()}")
        out.append("")

    return out


def _export_column_stats(c: sqlite3.Cursor) -> list[str]:
    """Estadísticas por columna para tablas principales — todo dinámico."""
    out = [_section("ESTADÍSTICAS POR COLUMNA (Tablas Principales)")]

    # Detectar tablas principales: las que tienen más de 0 filas
    c.execute("""
        SELECT name FROM sqlite_master WHERE type='table'
        AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'
        ORDER BY name
    """)
    all_tables = [r[0] for r in c.fetchall()]

    # Solo tablas con datos significativos (>10 filas)
    significant_tables = []
    for t in all_tables:
        count = _safe_count(c, t)
        if count > 10:
            significant_tables.append((t, count))

    if not significant_tables:
        out.append("  (sin tablas con datos suficientes)")
        out.append("")
        return out

    for table_name, count in significant_tables:
        cols = _get_columns(c, table_name)

        # Buscar columnas numéricas (INTEGER, REAL)
        numeric_cols = []
        for col_name in cols:
            try:
                c.execute(f"SELECT typeof(\"{col_name}\") FROM \"{table_name}\" WHERE \"{col_name}\" IS NOT NULL LIMIT 1")
                type_val = c.fetchone()
                if type_val and type_val[0] in ('integer', 'real'):
                    numeric_cols.append(col_name)
            except sqlite3.OperationalError:
                pass

        if not numeric_cols:
            continue

        out.append(_subsection(f"{table_name} ({count} filas)"))

        header = f"  {'Columna':<25} {'Mín':<15} {'Máx':<15} {'Promedio':<15} {'No Nulos':<10}"
        out.append(header)
        out.append("  " + "-" * 80)

        for col_name in numeric_cols:
            try:
                c.execute(f"""
                    SELECT MIN("{col_name}"), MAX("{col_name}"),
                           ROUND(AVG("{col_name}"), 2), COUNT("{col_name}")
                    FROM "{table_name}"
                """)
                min_val, max_val, avg_val, non_null = c.fetchone()

                min_str = f"{min_val:.2f}" if isinstance(min_val, float) else str(min_val) if min_val is not None else "-"
                max_str = f"{max_val:.2f}" if isinstance(max_val, float) else str(max_val) if max_val is not None else "-"
                avg_str = f"{avg_val:.2f}" if isinstance(avg_val, float) else str(avg_val) if avg_val is not None else "-"

                out.append(f"  {col_name:<25} {min_str:<15} {max_str:<15} {avg_str:<15} {non_null:<10}")
            except sqlite3.OperationalError:
                pass

        out.append("")

    return out


def _export_semantic_architecture(c: sqlite3.Cursor) -> list[str]:
    """Arquitectura semántica completa — 100% dinámico desde la DB."""
    out = [_section("ARQUITECTURA SEMÁNTICA")]

    # Tipos de dimensión
    if _table_exists(c, "tipos_dimension"):
        out.append(_subsection("TIPOS DE DIMENSIÓN (Ejes)"))
        cols = _get_columns(c, "tipos_dimension")

        c.execute("SELECT * FROM tipos_dimension ORDER BY id")
        rows = c.fetchall()

        if rows:
            header = "  " + " ".join(f"{col[:20]:<22}" for col in cols)
            out.append(header)
            out.append("  " + "-" * (22 * len(cols)))
            for row in rows:
                line = "  "
                for i, val in enumerate(row):
                    formatted = _format_value(val, cols[i] if i < len(cols) else "")
                    line += f"{formatted[:20]:<22} "
                out.append(line)
        out.append("")

    # Dimensiones por tipo
    if _table_exists(c, "dimensiones_semanticas") and _table_exists(c, "tipos_dimension"):
        out.append(_subsection("DIMENSIONES POR EJE"))

        # Obtener todos los tipos
        c.execute("SELECT id, nombre FROM tipos_dimension ORDER BY id")
        tipos = c.fetchall()

        for tipo_id, tipo_nombre in tipos:
            c.execute("""
                SELECT COUNT(*) FROM dimensiones_semanticas WHERE tipo_id = ?
            """, (tipo_id,))
            count = c.fetchone()[0]

            if count == 0:
                continue

            out.append(f"  {tipo_nombre} ({count} dimensiones):")

            # Listar dimensiones de este tipo
            c.execute("""
                SELECT name FROM dimensiones_semanticas
                WHERE tipo_id = ? ORDER BY name
            """, (tipo_id,))
            dims = [r[0] for r in c.fetchall()]

            # Mostrar en líneas de ~80 chars
            line = "    "
            for dim in dims:
                if len(line) + len(dim) + 2 > 78:
                    out.append(line)
                    line = "    "
                line += dim + ", "
            if line.rstrip().endswith(","):
                line = line.rstrip()[:-1]
            out.append(line)
            out.append("")

    # Distribución de dimensiones por uso en largo_plazo
    if _table_exists(c, "largo_plazo_dimensiones") and _table_exists(c, "dimensiones_semanticas"):
        out.append(_subsection("DIMENSIONES MÁS USADAS (Top 15)"))
        c.execute("""
            SELECT ds.name, COUNT(lp.concepto) as uso
            FROM largo_plazo_dimensiones lp
            JOIN dimensiones_semanticas ds ON lp.dimension_id = ds.id
            GROUP BY ds.name
            ORDER BY uso DESC
            LIMIT 15
        """)
        rows = c.fetchall()
        if rows:
            out.append(f"  {'Dimensión':<30} {'Nodos':<8}")
            out.append("  " + "-" * 38)
            for name, uso in rows:
                out.append(f"  {name:<30} {uso:<8}")
        out.append("")

    # Grupos semánticos WordNet
    if _table_exists(c, "grupos_semanticos") and _table_exists(c, "nodo_grupos_semanticos"):
        out.append(_subsection("GRUPOS WORDNET POR CATEGORÍA"))
        c.execute("""
            SELECT gs.nombre, COUNT(DISTINCT ngs.concepto) as nodos
            FROM grupos_semanticos gs
            JOIN nodo_grupos_semanticos ngs ON gs.id = ngs.grupo_id
            GROUP BY gs.nombre
            ORDER BY nodos DESC
        """)
        rows = c.fetchall()
        if rows:
            out.append(f"  {'Grupo':<35} {'Nodos Únicos':<12}")
            out.append("  " + "-" * 47)
            for name, nodos in rows:
                out.append(f"  {name:<35} {nodos:<12}")
        out.append("")

    return out


# ── Función principal ───────────────────────────────────────────────────────

def exportar(db_path: str, output_path: str | None = None) -> str:
    if output_path is None:
        output_path = OUTPUT_PATH

    if not os.path.exists(db_path):
        print(f"Error: base de datos no encontrada en {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    out: list[str] = []

    # Todo dinámico - lee de la DB en tiempo real
    out.extend(_export_header(db_path))
    out.extend(_export_db_info(c))
    out.extend(_export_schema(c))

    tables = _get_tables(c)

    out.extend(_export_categories(c))
    out.extend(_export_stats(c))
    out.extend(_export_fts_config(c))
    out.extend(_export_indexes(c))
    out.extend(_export_topology(c))
    out.extend(_export_metrics(c))
    out.extend(_export_semantic_groups(c))
    out.extend(_export_foreign_keys(c))
    out.extend(_export_column_stats(c))
    out.extend(_export_semantic_architecture(c))

    conn.close()

    result = "\n".join(out)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Exportado a: {output_path}")
    print(f"Contenido:   {len(result):,} caracteres")
    return output_path


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    exportar(db)
