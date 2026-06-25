#!/usr/bin/env python3
"""Exporta la arquitectura completa de la DB BioRAG a un archivo de texto plano.

Genera un blueprint autodescriptivo que cualquier IA puede leer para entender
la estructura, estado actual y filosofía del sistema BioRAG.

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


# ── Documentación arquitectónica incrustada ─────────────────────────────────

_DOC_INTRO = """\
Este archivo es un blueprint autodescriptivo generado automáticamente por
export_architecture.py. Contiene la estructura completa de la base de datos,
el estado actual de la memoria, y la documentación arquitectónica del sistema.

BioRAG es un motor de memoria persistente para agentes de IA que emula de
forma nativa el comportamiento de una base de datos vectorial a través de
topología de grafos sinápticos y lógica relacional, sin depender de embeddings,
modelos de ML ni infraestructura externa. Desarrollado en Python puro con
SQLite + FTS5.
"""

_DOC_CATEGORIES = """\
Cada categoría tiene un decay_rate que controla qué tan rápido decae el peso
sináptico durante el ciclo de sueño. Valores bajos = memorias persistentes.

  Profile  (0.05) — Identidad, casi nunca se olvida
  Principle (0.2) — Reglas y directivas fundamentales
  Protocol (0.5) — Procedimientos operativos
  System   (1.0) — Configuración de sistema
  Architecture (1.0) — Decisiones de diseño
  Lesson   (1.0) — Lecciones aprendidas
  Personal (1.0) — Datos personales del usuario
  Cognition (1.0) — Metacognición y auto-reflexión
  Relation (1.0) — Relaciones entre entidades
  Project  (1.5) — Proyectos temporales, olvido rápido
  General  (2.0) — Miscelánea, mayor decaimiento
"""

_DOC_SLEEP_CYCLE = """\
1. Consolidar corto_plazo → largo_plazo (borrar de corto_plazo durante el loop)
2. Auto-vincular (aristas por solapamiento de tokens con overlap coefficient)
3. LTD diferenciado: peso -= 0.05 * decay_rate (solo nodos activos)
4. Decay sináptico: sinapsis con ultimo_uso > 7 días: peso *= 0.95
5. Podar sinapsis muertas (peso < 0.05)
6. Dormir nodos débiles (peso <= 0.05)
7. Inhibición lateral si energía total > límite (n_activos * 1.6, mín 10.0)
8. Registrar métricas en metricas_cognitivas
9. Benchmark de rendimiento (latencia, tamaño DB)
10. Evicción opcional (BIORAG_PODAR=true): borrar dormidos con peso <= 0.01
"""

_DOC_SCORE = """\
Score híbrido de búsqueda:
  60% BM25 (relevancia textual via FTS5 trigram) + peso diferencial por centralidad en la red
+ 25% peso sináptico (largo_plazo.peso_sinaptico — frecuencia de uso)
+ 15% riqueza de asociaciones (número de vecinos en tabla sinapsis)

Peso diferencial: tokens con más conexiones en sinapsis + equivalencias en semántica
pesan más en el scoring. Peso base mínimo de 0.1 para que ningún término desaparezca.
"""

_DOC_ACTIVATION = """\
Al evocar un nodo:
  - Se propaga activación +0.05 a todos sus vecinos en la tabla sinapsis
  - Si el nodo estaba dormido, se despierta con +0.15 de peso
  - LTP al consolidar: +0.20 de peso sináptico
  - LTP al evocar: +0.15 de peso sináptico
"""

_DOC_PIPELINE = """\
Pipeline de búsqueda de 8 capas (buscar_por_frase):

  Fallback 1.0: FTS5 AND — búsqueda exacta con trigram tokenizer
  Fallback 1.3: FTS5 OR — si AND devuelve pocos, probar OR entre palabras
  Fallback 1.5: Expansión semántica — tabla semantica: auto→vehículo, bug→error
  Fallback 1.7: Similitud conceptual latente (Jaccard vecinos + tokens contenido)
    - Fórmula: 60% red sináptica + 40% contenido
    - Busca nodos "puente" que contengan tokens del query via FTS5
    - Calcula Jaccard entre vecinos de puentes y vecinos del nodo destino
    - Umbral: 0.10, máximo 5 resultados
  Fallback 1.8: Snap reciente — busca primero en nodos de los últimos 7 días
  Fallback 1.9: Evocación por cadena — multi-hop con decay logarítmico (1/(2^salto))
  Fallback 2.0: Substring match en contenido (LIKE %query%)
  Fallback 2.5: Best-word trigram similarity (tolerancia a typos, umbral 0.5)

Este pipeline es lo que permite que BioRAG emule el comportamiento de una base
de datos vectorial sin embeddings: la capa 1.5 expande semánticamente, la capa
1.7 encuentra relaciones conceptuales por topología de grafo, y la capa 2.5
tolera errores tipográficos por similitud de caracteres.
"""

_DOC_SIMILARITY = """\
Módulo: core/similitud_conceptual.py

  jaccard_vecinos(cursor, concepto_a, concepto_b) → float [0,1]
  similitud_por_contenido(query_tokens, contenido_tokens) → float [0,1]
  score_similitud_latente(cursor, query_tokens, nodo_concepto, nodo_contenido)
    → float [0,1] — Fórmula: 60% red + 40% contenido
  buscar_por_similitud_latente(cursor, frase, limite, umbral) → list
"""

_DOC_SEMANTICS = """\
Módulo: core/semantica.py

  expandir_query(cursor, termino, max_equivalentes) → list
  agregar_equivalencia(cursor, termino, equivalente, peso)
  eliminar_equivalencia(cursor, termino, equivalente)
  listar_equivalencias(cursor, termino) → list
  cargar_vocabulario(cursor, vocabulario_dict) → int
  auto_aprender_desde_sinonimos(cursor, concepto, sinonimos) → int

La tabla semantica es bidireccional: si "auto"→"vehículo" existe, también
existe "vehículo"→"auto". Esto permite expansión de queries sin embeddings.
"""

_DOC_MCP_TOOLS = """\
biorag_guardar(concepto, contenido, cat, syn)    — Guardar en corto plazo
biorag_buscar(query, cat, limite, deep, completo, asociados) — Búsqueda 8 capas
biorag_sueno(limite_energia)                     — Ciclo de consolidación
biorag_estado()                                  — Estadísticas de la corteza
biorag_corteza()                                 — Listar todos los nodos
biorag_asociar(a, b)                             — Crear sinapsis manual
biorag_leer_mensajes(para, no_leidos, ultimos)   — Leer canal inter-agente
biorag_comunicar(origen, destino, mensaje)        — Enviar mensaje
biorag_listar_categorias()                       — Las 11 categorías madre
biorag_sync_status()                             — Categorías pendientes sync
biorag_export_sync()                             — Export pendientes .jsonl.txt
biorag_export_full()                             — Export completo
biorag_contexto_inicio(agente, contexto)         — Inicia sesión (buffer)
biorag_contexto_fin(agente, resumen)             — Fin sesión + auto-sueño
biorag_metricas_historial(n=10)                  — Últimos N ciclos + tendencias
biorag_semantica_admin(accion, ...)              — CRUD tabla semántica
"""


# ── Funciones de exportación ────────────────────────────────────────────────

def _section(title: str) -> str:
    return f"\n{'=' * 70}\n  {title}\n{'=' * 70}\n"


def _subsection(title: str) -> str:
    return f"\n--- {title} ---\n"


def _export_header(db_path: str) -> list[str]:
    out = []
    out.append("=" * 70)
    out.append("  BioRAG — Database Architecture Export (Blueprint Completo)")
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
    out.append(_DOC_INTRO)
    return out


def _export_schema(c: sqlite3.Cursor) -> list[str]:
    out = [_section("ESQUEMA DE LA BASE DE DATOS")]

    out.append(_subsection("TABLAS"))
    c.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND sql IS NOT NULL ORDER BY name"
    )
    for name, sql in c.fetchall():
        count = c.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
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
    out.append(_DOC_CATEGORIES)

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

    total = c.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    activos = c.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
    ).fetchone()[0]
    dormidos = c.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'"
    ).fetchone()[0]
    sinapsis = c.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    sem_total = c.execute("SELECT COUNT(*) FROM semantica").fetchone()[0]
    sem_terms = c.execute(
        "SELECT COUNT(DISTINCT termino) FROM semantica"
    ).fetchone()[0]
    backup_count = c.execute("SELECT COUNT(*) FROM largo_plazo_backup").fetchone()[0]
    corto = c.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
    comms = c.execute("SELECT COUNT(*) FROM comunicaciones").fetchone()[0]

    energia = c.execute(
        "SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado='activo'"
    ).fetchone()[0] or 0

    out.append(f"  Nodos totales:          {total}")
    out.append(f"  Nodos activos:          {activos}")
    out.append(f"  Nodos dormidos:         {dormidos}")
    out.append(f"  Energía sináptica:      {energia}")
    out.append(f"  Aristas sinápticas:     {sinapsis}")
    out.append(f"  Equivalencias semánt.:  {sem_total} ({sem_terms} términos únicos)")
    out.append(f"  Entradas de backup:     {backup_count}")
    out.append(f"  En corto plazo (pend.): {corto}")
    out.append(f"  Comunicaciones totales: {comms}")
    out.append("")

    # Distribución por categoría
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
    """Extra: análisis de topología del grafo sináptico."""
    out = [_section("TOPOLOGÍA DEL GRAFO SINÁPTICO")]

    # Distribución de tipos de arista
    out.append(_subsection("DISTRIBUCIÓN POR TIPO DE ARISTA"))
    c.execute("""
        SELECT tipo, COUNT(*), ROUND(AVG(peso), 3), ROUND(MIN(peso), 3), ROUND(MAX(peso), 3)
        FROM sinapsis GROUP BY tipo ORDER BY COUNT(*) DESC
    """)
    out.append(f"{'Tipo':<22} {'Cantidad':<10} {'Peso Prom.':<12} {'Mín':<8} {'Máx':<8}")
    out.append("-" * 60)
    for tipo, cnt, avg_p, min_p, max_p in c.fetchall():
        out.append(f"{tipo:<22} {cnt:<10} {avg_p:<12} {min_p:<8} {max_p:<8}")
    out.append("")

    # Orígenes y destinos únicos
    origenes = c.execute("SELECT COUNT(DISTINCT origen) FROM sinapsis").fetchone()[0]
    destinos = c.execute("SELECT COUNT(DISTINCT destino) FROM sinapsis").fetchone()[0]
    out.append(f"  Nodos origen únicos:  {origenes}")
    out.append(f"  Nodos destino únicos: {destinos}")
    out.append("")

    return out


def _export_metrics(c: sqlite3.Cursor) -> list[str]:
    """Extra: historial de ciclos de sueño y métricas de rendimiento."""
    out = [_section("MÉTRICAS COGNITIVAS (últimos ciclos de sueño)")]

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

    # Métricas de rendimiento
    out.append(_subsection("MÉTRICAS DE RENDIMIENTO (últimas mediciones)"))
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


def _truncate(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    text = " ".join(text.split())  # normalizar espacios y newlines
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _export_memory_snapshot(c: sqlite3.Cursor) -> list[str]:
    out = [_section("SNAPSHOT DE MEMORIAS (largo_plazo)")]

    out.append(_subsection("NODOS ACTIVOS"))
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

    out.append(_subsection("NODOS DORMIDOS"))
    c.execute("""
        SELECT lp.concepto, c.name, lp.peso_sinaptico
        FROM largo_plazo lp
        JOIN categories c ON lp.categoria = c.id
        WHERE lp.estado = 'dormido'
        ORDER BY lp.peso_sinaptico DESC
    """)
    dormidos = c.fetchall()
    if dormidos:
        out.append(f"{'Concepto':<55} {'Categoría':<15} {'Peso':<6}")
        out.append("-" * 76)
        for concepto, cat, peso in dormidos:
            out.append(f"{concepto:<55} {cat:<15} {peso:<6}")
    else:
        out.append("  (ninguno)")
    out.append("")

    # Corto plazo pendiente
    out.append(_subsection("CORTO PLAZO (pendiente de consolidación)"))
    c.execute("""
        SELECT cp.concepto, c.name, cp.contenido
        FROM corto_plazo cp
        LEFT JOIN categories c ON cp.categoria = c.id
    """)
    rows = c.fetchall()
    if rows:
        for concepto, cat, contenido in rows:
            out.append(f"  [{cat or 'General'}] {concepto}")
            out.append(f"    {_truncate(contenido)}")
            out.append("")
    else:
        out.append("  (vacío — todo consolidado)")
    out.append("")

    return out


def _export_synapses(c: sqlite3.Cursor) -> list[str]:
    out = [_section("GRAFO SINÁPTICO (aristas)")]

    c.execute("""
        SELECT origen, destino, peso, tipo
        FROM sinapsis
        ORDER BY peso DESC
    """)
    rows = c.fetchall()

    out.append(f"Total aristas: {len(rows)}")
    out.append("")
    out.append(f"{'Origen':<45} {'Destino':<45} {'Peso':<7} {'Tipo':<18}")
    out.append("-" * 115)
    for origen, destino, peso, tipo in rows:
        out.append(f"{origen:<45} {destino:<45} {peso:<7.3f} {tipo:<18}")
    out.append("")
    return out


def _export_semantics(c: sqlite3.Cursor) -> list[str]:
    out = [_section("TESAURO SEMÁNTICO (equivalencias)")]

    c.execute("SELECT COUNT(*) FROM semantica")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT termino) FROM semantica")
    terms = c.fetchone()[0]

    out.append(f"Total equivalencias: {total}")
    out.append(f"Términos únicos: {terms}")
    out.append("")

    # Agrupar por término
    c.execute("""
        SELECT termino, GROUP_CONCAT(equivalente || ' (' || peso || ')', ', ')
        FROM semantica
        GROUP BY termino
        ORDER BY termino
    """)
    out.append(f"{'Término':<25} Equivalencias")
    out.append("-" * 80)
    for termino, equivs in c.fetchall():
        out.append(f"{termino:<25} {equivs}")
    out.append("")
    return out


def _export_communications(c: sqlite3.Cursor) -> list[str]:
    """Extra: últimos mensajes del canal inter-agente."""
    out = [_section("COMUNICACIONES ENTRE AGENTES (últimos 10)")]

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


def _export_documentation() -> list[str]:
    """Genera las secciones de documentación arquitectónica."""
    out = [_section("DOCUMENTACIÓN ARQUITECTÓNICA")]

    out.append(_subsection("CICLO DE CONSOLIDACIÓN (sueño)"))
    out.append(_DOC_SLEEP_CYCLE)

    out.append(_subsection("SCORE HÍBRIDO (búsqueda)"))
    out.append(_DOC_SCORE)

    out.append(_subsection("PROPAGACIÓN DE ACTIVACIÓN (spreading activation)"))
    out.append(_DOC_ACTIVATION)

    out.append(_subsection("PIPELINE DE BÚSQUEDA (8 capas)"))
    out.append(_DOC_PIPELINE)

    out.append(_subsection("SIMILITUD CONCEPTUAL LATENTE"))
    out.append(_DOC_SIMILARITY)

    out.append(_subsection("EXPANSIÓN SEMÁNTICA"))
    out.append(_DOC_SEMANTICS)

    out.append(_subsection("HERRAMIENTAS MCP (16 tools)"))
    out.append(_DOC_MCP_TOOLS)

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

    # 1. Header con metadata
    out.extend(_export_header(db_path))

    # 2. Esquema DDL dinámico
    out.extend(_export_schema(c))

    # 3. Categorías con decay
    out.extend(_export_categories(c))

    # 4. Estadísticas globales
    out.extend(_export_stats(c))

    # 5. Topología del grafo (extra)
    out.extend(_export_topology(c))

    # 6. Métricas cognitivas y rendimiento (extra)
    out.extend(_export_metrics(c))

    # 11. Documentación arquitectónica
    out.extend(_export_documentation())

    conn.close()

    result = "\n".join(out)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Exportado a: {output_path}")
    print(f"Contenido:   {len(result):,} caracteres")
    print(f"Secciones:   7 (esquema, categorías, estadísticas, topología,")
    print(f"             métricas, rendimiento, documentación)")
    return output_path


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    exportar(db)
