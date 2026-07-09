#!/usr/bin/env python3
"""Exporta la arquitectura completa de la DB BioRAG a un archivo de texto plano.

Genera un blueprint autodescriptivo que cualquier IA puede leer para entender
la estructura, estado actual y filosofía del sistema BioRAG.

TODO es dinámico: lee esquema, datos, stats directo de la DB.
Sin strings hardcodeados que queden obsoletos.

Uso:
    python3 scripts/export_architecture.py [ruta_db]
"""

import sqlite3
import os
import sys
import re
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


def _truncate(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _table_exists(c: sqlite3.Cursor, table_name: str) -> bool:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return c.fetchone() is not None


def _column_exists(c: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    c.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in c.fetchall())


def _safe_count(c: sqlite3.Cursor, table: str, where: str = "") -> int:
    try:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        c.execute(sql)
        return c.fetchone()[0]
    except sqlite3.OperationalError:
        return 0


# ── Exportación dinámica ────────────────────────────────────────────────────

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
    out = [_section("CATEGORÍAS")]

    if not _table_exists(c, "categories"):
        out.append("(tabla categories no existe)")
        return out

    out.append("decay_rate controla decaimiento durante ciclo de sueño.")
    out.append("Valores bajos = memorias persistentes.")
    out.append("")

    c.execute("SELECT id, name, description, decay_rate FROM categories ORDER BY id")
    rows = c.fetchall()
    out.append(f"{'ID':<4} {'Nombre':<15} {'Decay':<7} Descripción")
    out.append("-" * 60)
    for cid, name, desc, decay in rows:
        out.append(f"{cid:<4} {name:<15} {decay:<7} {desc}")
    out.append("")
    return out


def _export_stats(c: sqlite3.Cursor) -> list[str]:
    out = [_section("ESTADÍSTICAS ACTUALES")]

    # Conteos dinámicos de todas las tablas
    out.append(_subsection("CONTEOS POR TABLA"))
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]
    for table in tables:
        count = _safe_count(c, table)
        out.append(f"  {table:<35} {count:>8} filas")
    out.append("")

    # Detalle de largo_plazo si existe
    if _table_exists(c, "largo_plazo"):
        out.append(_subsection("LARGO PLAZO"))
        activos = _safe_count(c, "largo_plazo", "estado = 'activo'")
        dormidos = _safe_count(c, "largo_plazo", "estado = 'dormido'")
        total = _safe_count(c, "largo_plazo")

        try:
            c.execute("SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado='activo'")
            energia = c.fetchone()[0] or 0
        except sqlite3.OperationalError:
            energia = 0

        out.append(f"  Total:           {total}")
        out.append(f"  Activos:         {activos}")
        out.append(f"  Dormidos:        {dormidos}")
        out.append(f"  Energía total:   {energia}")
        out.append("")

        # Distribución por categoría
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


def _export_topology(c: sqlite3.Cursor) -> list[str]:
    out = [_section("TOPOLOGÍA DEL GRAFO SINÁPTICO")]

    if not _table_exists(c, "sinapsis"):
        out.append("(tabla sinapsis no existe)")
        return out

    # Distribución de tipos de arista
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

    # Orígenes y destinos únicos
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
    out = [_section("MÉTRICAS COGNITIVAS")]

    if _table_exists(c, "metricas_cognitivas"):
        out.append(_subsection("ÚLTIMOS CICLOS DE SUEÑO"))
        c.execute("""
            SELECT timestamp, nodos_consolidados, nodos_dormidos_ciclo,
                   sinapsis_creadas, sinapsis_podadas, categoria_dominante,
                   ratio_consolidacion
            FROM metricas_cognitivas ORDER BY timestamp DESC LIMIT 5
        """)
        rows = c.fetchall()
        if rows:
            out.append(
                f"{'Fecha':<22} {'Consolid.':<10} {'Dormidos':<10} "
                f"{'Sin.Crea.':<10} {'Sin.Pod.':<10} {'Cat.Dom.':<12} {'Ratio':<8}"
            )
            out.append("-" * 82)
            for ts, cons, dorm, s_cre, s_pod, cat_dom, ratio in rows:
                fecha = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                out.append(
                    f"{fecha:<22} {cons:<10} {dorm:<10} "
                    f"{s_cre:<10} {s_pod:<10} {cat_dom or '-':<12} {ratio:<8}"
                )
        else:
            out.append("  (sin ciclos de sueño registrados)")
        out.append("")

    if _table_exists(c, "metricas_rendimiento"):
        out.append(_subsection("MÉTRICAS DE RENDIMIENTO"))
        c.execute("""
            SELECT timestamp, total_nodos, nodos_activos, total_dormidos,
                   latencia_busqueda_ms, tamano_db_bytes, energia_sinaptica
            FROM metricas_rendimiento ORDER BY timestamp DESC LIMIT 3
        """)
        rows = c.fetchall()
        if rows:
            out.append(
                f"{'Fecha':<22} {'Nodos':<7} {'Act.':<6} {'Dorm.':<7} "
                f"{'Latencia':<10} {'DB Size':<12} {'Energía':<8}"
            )
            out.append("-" * 72)
            for ts, tot, act, dorm, lat, db_sz, energ in rows:
                fecha = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                db_kb = f"{db_sz / 1024:.0f} KB"
                out.append(
                    f"{fecha:<22} {tot:<7} {act:<6} {dorm:<7} "
                    f"{lat:<10.2f} {db_kb:<12} {energ:<8}"
                )
        else:
            out.append("  (sin mediciones de rendimiento)")
        out.append("")

    return out


def _export_memory_snapshot(c: sqlite3.Cursor) -> list[str]:
    out = [_section("SNAPSHOT DE MEMORIAS")]

    if not _table_exists(c, "largo_plazo"):
        out.append("(tabla largo_plazo no existe)")
        return out

    # Nodos activos
    out.append(_subsection("NODOS ACTIVOS"))
    try:
        if _table_exists(c, "categories") and _column_exists(c, "largo_plazo", "categoria"):
            c.execute("""
                SELECT lp.concepto, c.name, lp.peso_sinaptico, lp.sinonimos,
                       lp.contenido
                FROM largo_plazo lp
                JOIN categories c ON lp.categoria = c.id
                WHERE lp.estado = 'activo'
                ORDER BY lp.peso_sinaptico DESC
            """)
            for concepto, cat, peso, syn, contenido in c.fetchall():
                out.append(f"  [{cat}] {concepto} (peso: {peso})")
                if syn:
                    out.append(f"    Sinónimos: {syn}")
                out.append(f"    {_truncate(contenido)}")
                out.append("")
        else:
            c.execute("""
                SELECT concepto, peso_sinaptico, sinonimos, contenido
                FROM largo_plazo WHERE estado = 'activo'
                ORDER BY peso_sinaptico DESC
            """)
            for concepto, peso, syn, contenido in c.fetchall():
                out.append(f"  {concepto} (peso: {peso})")
                if syn:
                    out.append(f"    Sinónimos: {syn}")
                out.append(f"    {_truncate(contenido)}")
                out.append("")
    except sqlite3.OperationalError:
        out.append("  (error leyendo nodos)")

    # Nodos dormidos
    out.append(_subsection("NODOS DORMIDOS"))
    try:
        c.execute("""
            SELECT concepto, peso_sinaptico
            FROM largo_plazo WHERE estado = 'dormido'
            ORDER BY peso_sinaptico DESC
        """)
        dormidos = c.fetchall()
        if dormidos:
            out.append(f"{'Concepto':<55} {'Peso':<6}")
            out.append("-" * 61)
            for concepto, peso in dormidos:
                out.append(f"{concepto:<55} {peso:<6}")
        else:
            out.append("  (ninguno)")
    except sqlite3.OperationalError:
        out.append("  (error leyendo nodos)")
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
    out = [_section("GRAFO SINÁPTICO (aristas)")]

    if not _table_exists(c, "sinapsis"):
        out.append("(tabla sinapsis no existe)")
        return out

    c.execute("""
        SELECT origen, destino, peso, tipo
        FROM sinapsis
        ORDER BY peso DESC
    """)
    rows = c.fetchall()

    out.append(f"Total aristas: {len(rows)}")
    out.append("")
    if rows:
        out.append(f"{'Origen':<45} {'Destino':<45} {'Peso':<7} {'Tipo':<18}")
        out.append("-" * 115)
        for origen, destino, peso, tipo in rows:
            out.append(f"{origen:<45} {destino:<45} {peso:<7.3f} {tipo:<18}")
    else:
        out.append("  (sin aristas)")
    out.append("")
    return out


def _export_semantic_groups(c: sqlite3.Cursor) -> list[str]:
    """Exporta grupos semánticos WordNet si existen."""
    out = [_section("GRUPOS SEMÁNTICOS (WordNet)")]

    if not _table_exists(c, "grupos_semanticos"):
        out.append("(tabla grupos_semanticos no existe — WordNet no configurado)")
        return out

    c.execute("SELECT COUNT(*) FROM grupos_semanticos")
    total_grupos = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodo_grupos_semanticos")
    total_rel = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT concepto) FROM nodo_grupos_semanticos")
    nodos_clasificados = c.fetchone()[0]

    out.append(f"  Grupos:            {total_grupos}")
    out.append(f"  Relaciones:        {total_rel}")
    out.append(f"  Nodos clasificados: {nodos_clasificados}")
    out.append("")

    # Top 10 grupos por uso
    out.append(_subsection("TOP 10 GRUPOS POR USO"))
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
        out.append(f"{'Grupo':<30} {'Nodos':<8}")
        out.append("-" * 38)
        for nombre, uso in rows:
            out.append(f"{nombre:<30} {uso:<8}")
    out.append("")

    return out


def _export_communications(c: sqlite3.Cursor) -> list[str]:
    out = [_section("COMUNICACIONES ENTRE AGENTES (últimos 10)")]

    if not _table_exists(c, "comunicaciones"):
        out.append("(tabla comunicaciones no existe)")
        return out

    c.execute("""
        SELECT origen, destino, contenido, timestamp, leido
        FROM comunicaciones
        ORDER BY timestamp DESC LIMIT 10
    """)
    rows = c.fetchall()
    if rows:
        for origen, destino, contenido, ts, leido in rows:
            fecha = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            estado = "leído" if leido else "NO LEÍDO"
            out.append(f"  [{fecha}] {origen} → {destino} ({estado})")
            out.append(f"    {_truncate(contenido, 300)}")
            out.append("")
    else:
        out.append("  (sin mensajes)")
    out.append("")
    return out


def _export_fts_config(c: sqlite3.Cursor) -> list[str]:
    """Exporta configuración de FTS5 si existe."""
    out = [_section("CONFIGURACIÓN FTS5")]

    fts_tables = []
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
            c.execute(f"SELECT COUNT(*) FROM {fts_table}")
            count = c.fetchone()[0]
            out.append(f"  Documentos indexados: {count}")
        except sqlite3.OperationalError:
            out.append(f"  (no se pudo leer)")
        out.append("")

    return out


def _export_indexes(c: sqlite3.Cursor) -> list[str]:
    """Exporta índices personalizados."""
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


def _export_db_info(c: sqlite3.Cursor) -> list[str]:
    """Info general de la DB."""
    out = [_section("INFORMACIÓN DE LA BASE DE DATOS")]

    try:
        c.execute("PRAGMA journal_mode")
        journal = c.fetchone()[0]
        out.append(f"  Journal mode:    {journal}")
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
        free = c.fetchone()[0]
        out.append(f"  Páginas libres:  {free}")
    except sqlite3.OperationalError:
        pass

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
    out.extend(_export_categories(c))
    out.extend(_export_stats(c))
    out.extend(_export_fts_config(c))
    out.extend(_export_indexes(c))
    out.extend(_export_topology(c))
    out.extend(_export_metrics(c))
    out.extend(_export_semantic_groups(c))
    out.extend(_export_memory_snapshot(c))
    out.extend(_export_synapses(c))
    out.extend(_export_communications(c))

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
