#!/usr/bin/env python3
"""generate_domain_dict.py — Genera diccionario de dominio automáticamente desde nodos existentes.

Extrae términos técnicos, abreviaturas y sinónimos del contenido de los nodos
y crea una tabla SQLite para expansión automática de queries.

USO:
    python3 scripts/generate_domain_dict.py [--db PATH]

Salida: Tabla concept_hub_domain_dict en la DB, con mapeos term → synonyms.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def crear_tabla_domain_dict(conn: sqlite3.Connection) -> None:
    """Crea la tabla domain_dict si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_hub_domain_dict (
            term TEXT PRIMARY KEY,
            synonyms TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'technical',
            frequency INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_domain_dict_category
        ON concept_hub_domain_dict(category)
    """)
    conn.commit()


def extraer_terminos_tecnicos(conn: sqlite3.Connection) -> dict[str, Counter]:
    """Extrae términos técnicos del contenido de los nodos.
    
    Returns:
        Dict de term → Counter(frecuencia, categorías)
    """
    cursor = conn.execute(
        "SELECT concepto, contenido, sinonimos FROM largo_plazo WHERE estado = 'activo'"
    )
    
    terminos = Counter()
    term_contextos = {}  # term → set de contextos donde aparece
    
    # Patrones de términos técnicos
    patron_tecnico = re.compile(
        r'\b(?:'
        r'[A-Z]{2,}|'  # Abreviaturas: API, SQL, BM25
        r'\w+(?:_\w+)+|'  # snake_case: memory_store, buscar_por_frase
        r'\w+(?:-\w+)+|'  # kebab-case: concept-hub, test-concept-hub
        r'\w+\.py|'  # Archivos Python
        r'v\d+\.\d+|'  # Versiones: v22.1, v10.3
        r'(?:ft|ts|bm|jsd|ppmi|srl|hdc|sdm|rpe|qcr|jaccard|levenshtein)\b'  # Términos técnicos específicos
        r')',
        re.IGNORECASE
    )
    
    for concepto, contenido, sinonimos in cursor.fetchall():
        texto = f"{concepto} {contenido or ''} {sinonimos or ''}"
        
        # Encontrar términos técnicos
        for match in patron_tecnico.finditer(texto):
            term = match.group().lower().strip()
            if len(term) >= 3:
                terminos[term] += 1
                if term not in term_contextos:
                    term_contextos[term] = set()
                term_contextos[term].add(concepto)
    
    return terminos, term_contextos


def generar_sinonimosautomaticos(term: str, term_contextos: dict, conn: sqlite3.Connection) -> list[str]:
    """Genera sinónimos automáticos para un término basado en su contexto.
    
    Estrategia:
    1. Buscar nodos que contienen el término
    2. Extraer otras palabras técnicas de esos nodos
    3. Las palabras que co-ocurren frecuentemente son sinónimos contextuales
    """
    if term not in term_contextos:
        return []
    
    nodos = term_contextos[term]
    if len(nodos) < 2:
        return []
    
    # Contar co-ocurrencias
    co_ocurrencias = Counter()
    for concepto in nodos:
        cursor = conn.execute(
            "SELECT contenido FROM largo_plazo WHERE concepto = ?", (concepto,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            # Tokenizar contenido
            tokens = set(re.findall(r'\w{3,}', row[0].lower()))
            tokens.discard(term)
            for t in tokens:
                co_ocurrencias[t] += 1
    
    # Los sinónimos son palabras que co-ocurren en >= 2 nodos
    sinonimos = [t for t, count in co_ocurrencias.items() if count >= 2]
    return sinonimos[:10]  # Máx 10 sinónimos


def generar_domain_dict(db_path: str) -> int:
    """Genera el diccionario de dominio completo.
    
    Returns:
        Número de términos generados.
    """
    conn = sqlite3.connect(db_path)
    crear_tabla_domain_dict(conn)
    
    print(f"[INFO] Extrayendo términos técnicos de {db_path}...")
    terminos, term_contextos = extraer_terminos_tecnicos(conn)
    
    print(f"[INFO] Encontrados {len(terminos)} términos únicos")
    
    # Filtrar términos muy comunes (>50 apariciones) o muy raros (1 aparición)
    terminos_counter = Counter({
        term: count for term, count in terminos.items()
        if 2 <= count <= 50
    })
    
    print(f"[INFO] {len(terminos_counter)} términos después de filtrar")
    
    # Generar diccionario
    insertados = 0
    for term, frequency in terminos_counter.most_common():
        sinonimos = generar_sinonimosautomaticos(term, term_contextos, conn)
        
        if sinonimos:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO concept_hub_domain_dict 
                       (term, synonyms, category, frequency) 
                       VALUES (?, ?, 'technical', ?)""",
                    (term, ','.join(sinonimos), frequency)
                )
                insertados += 1
            except sqlite3.Error:
                pass
    
    conn.commit()
    
    # Estadísticas
    cursor = conn.execute("SELECT COUNT(*) FROM concept_hub_domain_dict")
    total = cursor.fetchone()[0]
    
    cursor = conn.execute(
        "SELECT category, COUNT(*) FROM concept_hub_domain_dict GROUP BY category"
    )
    categorias = cursor.fetchall()
    
    print(f"\n[RESULTADO] Diccionario generado:")
    print(f"  Total términos: {total}")
    for cat, count in categorias:
        print(f"  - {cat}: {count}")
    
    conn.close()
    return insertados


def main() -> int:
    parser = argparse.ArgumentParser(description="Generar diccionario de dominio automáticamente")
    parser.add_argument(
        "--db", 
        default=os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag.db"),
        help="Ruta a la DB de BioRAG"
    )
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"[ERROR] DB no encontrada: {args.db}")
        return 1
    
    count = generar_domain_dict(args.db)
    print(f"\n[OK] {count} términos insertados en concept_hub_domain_dict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
